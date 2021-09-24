#!flask/bin/python
import sys, os
sys.path.append(os.path.abspath(os.path.join('..', 'utils')))
from env import AWS_ACCESS_KEY, AWS_SECRET_ACCESS_KEY, AWS_REGION, DYNAMODB_TABLE
from flask import Flask, jsonify, abort, request, make_response, url_for
from flask import render_template, redirect
import time
import json
import boto3  
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime
from botocore.exceptions import ClientError
from datetime import timedelta

app = Flask(__name__, static_url_path="")

dynamodb = boto3.resource('dynamodb', aws_access_key_id=AWS_ACCESS_KEY,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                            region_name=AWS_REGION)

table = dynamodb.Table(DYNAMODB_TABLE)

@app.errorhandler(400)
def bad_request(error):
    """ 400 page route.

    get:
        description: Endpoint to return a bad request 400 page.
        responses: Returns 400 object.
    """
    return make_response(jsonify({'error': 'Bad request'}), 400)

@app.errorhandler(404)
def not_found(error):
    """ 404 page route.

    get:
        description: Endpoint to return a not found 404 page.
        responses: Returns 404 object.
    """
    return make_response(jsonify({'error': 'Not found'}), 404)


@app.route('/', methods=['GET'])
def home_page():
    timestamp = []
    sentiment = []
    now=int(time.time())
    timestampold=now-80000

    response = table.scan(
        FilterExpression=Attr('timestamp').gt(timestampold)
    )
    location = []
    count = 0
    items = response['Items']
    items = sorted(items, key=lambda x: x['timestamp'])
    sentiment_level = [0,0,0]
    for i in items:
        s = i['sentiment']
        dt = datetime.fromtimestamp(i['timestamp']/1000)
        dttime = str(dt.hour) + ':' + str(dt.minute) + ':' + str(dt.second)
        timestamp.append(dttime)
        sentiment.append(s)
        if s >= 1:
            sentiment_level[2] += 1
        elif s < 1 and s>=0:
            sentiment_level[1] += 1
        else:
            sentiment_level[0] += 1
        position = i['location'].split(',')
        
        location.append({'lat':float(position[0]), 'lon': float(position[1]), 'z':1})
        print(location)
    return render_template('index.html', timestamp = timestamp, sentiment = sentiment, sentiment_level = sentiment_level, location = location)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
