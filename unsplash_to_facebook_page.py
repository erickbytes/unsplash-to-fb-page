from unsplash.api import Api
from unsplash.auth import Auth
from datetime import datetime
import pandas as pd
from flask import Flask, url_for, redirect
import requests
import logging
import mysql.connector
import sys

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
app = Flask(__name__)

@app.route("/")
def index():
    photo_id = random_unsplash_photo()
    result = query_photo_in_db(photo_id)
    if result == "Do not post.":
        logging.info(f"Post aborted for photo id {photo_id}, already posted.")
        return redirect(url_for("get_quote"))
    access_token = page_access_token()
    access_token = get_token_from_db()
    download_url, status_code, response = facebook_page_post(photo_id, access_token)
    if status_code == 400:
        return "Facebook post failed"
    record_tuple = (photo_id, download_url, str(datetime.now()), status_code, response)
    add_photo_to_db(record_tuple)
    status = fb_post_status()
    if status != "Too soon.":
        # if it's time to make a post, route to home page.
        return redirect(url_for("confirmation_page"))
    html_page = """<html><head><link rel='stylesheet' href="/static/styles/styles.css">
                    <link rel="shortcut icon" type="image/x-icon" href="/static/favicon.ico">
                    <Title>Auto Facebook Page Poster</Title></head>
                    <body>
                    <div class="form">
                    <form action="/get_best_tacos" method="post">
                    <label for="zipcode">Enter your zip code for tacos near you!</label>
                    <input type="text" id ="zipcode" name="zipcode">
                    <input type="image" id="taco" src="/static/iStock-1084361584.jpg" border="0" alt="Submit" />
                    </form></div></body></html>"""
    return html_page
    return None


@app.route("/confirmation_page", methods=["GET", "POST"])
def confirmation_page():
    """Renders the HTML form to ask for the user's zip code."""
    html_page = """<html><head><link rel='stylesheet' href="/static/styles/styles.css">
                    <link rel="shortcut icon" type="image/x-icon" href="/static/tacofavicon.ico">
                    <Title>Facebook Post Status</Title></head>
                    <body>
                    <p>Your page post has been sent.</p></body></html>"""
    return html_page


def random_unsplash_photo():
    """Python-Unsplash library Github:
    https://github.com/yakupadakli/python-unsplash

    collection ids
    "Positive Thoughts Daily" = 66610223
    "Past Posts" = 32132785
    """
    client_id = "client_id"
    client_secret = "client_secret"
    redirect_uri = "redirect_uri"
    code = ""
    auth = Auth(client_id, client_secret, redirect_uri, code=code)
    api = Api(auth)
    # returns a python list containing a class
    photo = api.photo.random(collections=your_collection_id)
    photo_id = photo[0].id
    return photo_id


def unsplash_photo_download_url(photo_id):
    """Call the Unsplash API to get download url for photo.
    Accepts: photo id
    Returns: photo download url
    """
    client_id = "client_id"
    r = requests.get(
        url=f"https://api.unsplash.com/photos/{photo_id}/download?client_id={client_id}"
    )
    logging.info(r.text)
    logging.info(r.status_code)
    photo = r.json()
    logging.info(photo.keys())
    return photo["url"]


def add_photo_to_db(record_tuple):
    """Pass data as SQL parameters with mysql tto add photo from Unsplash API to DB.
    accepts: list of tuples for 4 columns"""
    try:
        conn = mysql.connector.connect(
            host="user.mysql.pythonanywhere-services.com",
            db="user$database",
            user="user_name",
            password="password",
        )
        cursor = conn.cursor()
        sql = """INSERT INTO Photos (photo_id, download_url, date, status_code, fb_result) VALUES (%s, %s, %s, %s, %s) """
        cursor.execute(sql, record_tuple)
        conn.commit()
    except mysql.connector.Error as error:
        logging.info("Failed to insert into MySQL table {}".format(error))
    except:
        logging.exception("Error inserting records to DB.")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
        return "MySQL connection is closed"


def query_photo_in_db(photo_id):
    """prevent duplicate posts by checking table named 'Photos'--> photos_df: pandas dataframe"""
    try:
        conn = mysql.connector.connect(
            host="user.mysql.pythonanywhere-services.com",
            db="user$database",
            user="user_name",
            password="password",
        )
        photos_df = pd.read_sql(sql="""SELECT * FROM Photos""", con=conn)
        if photo_id in list(photos_df.photo_id):
            logging.info("Grabbed an old photo. Standing by.")
            return "Do not post."
    except mysql.connector.Error as error:
        logging.info("Failed to insert into MySQL table {}".format(error))
    except:
        logging.exception("Error inserting records to DB.")
    finally:
        if conn.is_connected():
            conn.close()
        return "mysql DB connection closed."


def fb_post_status():
    """Check how long it's been since the last FB page post.
    Returns status --> str: message to indicate if a new fb post should be made."""
    try:
        conn = mysql.connector.connect(
            host="user.mysql.pythonanywhere-services.com",
            db="user$database",
            user="user_name",
            password="password",
        )
        photos_df = pd.read_sql(sql="""SELECT * FROM Photos""", con=conn)
        delta = datetime.now() - pd.to_datetime(photos_df.date).max()
        logging.info(f"days since last post: {delta.days}")
        hours_since_last_post = delta.seconds / 3600
        posts_number = photos_df.shape[0]
        if conn.is_connected():
            conn.close()
        if photos_df.empty:
            return "Ok to send."
        elif int(delta.days) == 0:
            logging.info("Too soon to post again.")
            return "Too soon."
        elif list(photos_df.status_code)[-1] != 200:
            return "Ok to send."
        else:
            return "Too soon."
    except mysql.connector.Error as error:
        logging.info("Failed to insert into MySQL table {}".format(error))
    except:
        logging.exception("Error inserting records to DB.")


def page_access_token():
    """this long lived token retrieved with curl on 1/15/2022, Good for 60 days"""
    long_token = "your_long_lived_token"
    return long_token


def sixty_day_token():
    """This token gets this message when used:

    {"error":{"message":"Unsupported post request. Object with ID '123456789' does not exist,
    cannot be loaded due to missing permissions, or does not support this operation.
    Please read the Graph API documentation at https:\/\/developers.facebook.com\/docs\/graph-api",
    "type":"GraphMethodException","code":100,"error_subcode":33,"fbtrace_id":"AhCRjvtgSjoCpgGGuZyDlKW"}}

    curl -i -X GET "https://graph.facebook.com/{your-user-id}/accounts?access_token={user-access-token}
    """
    logging.info("Trying to get new token...")
    app_token = "your_token"
    app_id = "your_app_id"
    url = f"https://graph.facebook.com/{app_id}/accounts?access_token={app_token}"
    r = requests.get(url)
    logging.info(r.text)
    logging.info(r.status_code)
    data = r.json()
    access_token = data["data"][0]["access_token"]
    return access_token


def add_token_to_db(access_token):
    """Pass data as SQL parameters with mysql tto add photo from Unsplash API to DB.
    accepts: list of tuples for 4 columns"""
    try:
        conn = mysql.connector.connect(
            host="user.mysql.pythonanywhere-services.com",
            db="user$database",
            user="user_name",
            password="password",
        )
        cursor = conn.cursor()
        sql = """INSERT INTO Tokens (token, date) VALUES (%s, %s) """
        record_tuple = (access_token, str(datetime.now()))
        cursor.execute(sql, record_tuple)
        conn.commit()
    except mysql.connector.Error as error:
        logging.info("Failed to insert into MySQL table {}".format(error))
    except:
        logging.exception("Error inserting records to DB.")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
        return "MySQL connection is closed"


def get_token_from_db():
    """Fetch last token retrieved from db. Returns token --> str: message to
    indicate if a new fb post should be made"""
    try:
        conn = mysql.connector.connect(
            host="user.mysql.pythonanywhere-services.com",
            db="user$database",
            user="user_name",
            password="password",
        )
        tokens_df = pd.read_sql(sql="""SELECT * FROM Tokens""", con=conn)
        token = list(tokens_df.token)[-1]
        if conn.is_connected():
            conn.close()
        return token
    except mysql.connector.Error as error:
        logging.info("Failed to insert into MySQL table {}".format(error))
    except:
        logging.exception("Error inserting records to DB.")


def facebook_page_post(photo_id, access_token):
    """Post a new image from unsplash to FB.

    accepts --> photo_id, str
    1) get download link with unsplash
    2) use the facebook api to post to page
    returns --> download_url: photo download url, unsplash API status code

    FB API Resources
    "Getting Started": https://developers.facebook.com/docs/pages/getting-started
    "Explorer": https://developers.facebook.com/tools/explorer
    app dashboard: https://developers.facebook.com/apps/your_app_id/dashboard/
    permissions reference: https://developers.facebook.com/docs/permissions/reference
    debugging tokens: https://developers.facebook.com/docs/facebook-login/access-tokens/debugging-and-error-handling/
    publishing: https://developers.facebook.com/docs/pages/publishing/

    Photos should be less than 4 MB and saved as JPG, PNG, GIF, TIFF or will not be uploaded (400 error)
    """
    try:
        logging.info("Making new FB post...")
        page_id = "your_page_id"
        download_url = unsplash_photo_download_url(photo_id)
        url = f"https://graph.facebook.com/{page_id}/photos?url={download_url}&access_token={access_token}"
        r = requests.post(url)
        logging.info(r.text)
        logging.info(r.status_code)
        logging.info("Requested new FB post...")
        # fetch new token and retry posting if 403 forbidden
        if "Error validating access token" in r.text:
            access_token = sixty_day_token()
            add_token_to_db(access_token)
            download_url, status_code, text = facebook_page_post(photo_id, access_token)
            return download_url, status_code, text
        if "should be less than 4 MB and saved as JPG, PNG, GIF, TIFF" in r.text:
            record_tuple = (
                photo_id,
                download_url,
                str(datetime.now()),
                r.status_code,
                r.text,
            )
            add_photo_to_db(record_tuple)
            return download_url, r.status_code, r.text
        return download_url, r.status_code, r.text
    except:
        logging.exception("Failed to make new Facebook post.")
