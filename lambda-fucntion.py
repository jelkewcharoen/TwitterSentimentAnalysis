import base64
import os
import json
import boto3
from botocore.exceptions import ClientError
from geopy.geocoders import Nominatim
from decimal import Decimal

geolocator = Nominatim(user_agent='twitterStream')
client = boto3.client('comprehend')
REGION="us-east-1"


'''
TERMS={}
sent_file = open('AFINN-111.txt')
sent_lines = sent_file.readlines()

for line in sent_lines:
    s = line.split("\t")

    TERMS[s[0]] = s[1].strip()

sent_file.close()
'''

def get_sentiment(text):
    '''splitTweet = text.split()
    sentiment = 0.0

    for word in splitTweet:
        if word in TERMS:
            sentiment = sentiment+ float(TERMS[word])

    return sentiment    '''
    sentiment = client.detect_sentiment(Text=text, LanguageCode='en')['Sentiment']
    if sentiment=='NEGATIVE':
        return -1
    elif sentiment=='POSITIVE':
        return 1
    else   
        return 0




def get_location(location):
    lat = 0
    lon = 0

    try:

        if location:
            location = geolocator.geocode(location)
            lat=location.raw['lat']
            lon=location.raw['lon']

    except:
        pass

    return f'''{str(lat)},{str(lon)}'''

def flattenData(tweet):
    output_json={}    
    output_json["id_str"] = tweet['id_str']
    output_json["timestamp"] = int(tweet['timestamp_ms'])
    output_json["tweet"] = tweet['text']
    output_json["location"] = tweet['user']['location']
    output_json['tweet_name'] = tweet['user']['name']
    output_json['tweet_text'] = tweet['text']        
    output_json['tweet_user_id'] = tweet['user']['screen_name']

    return output_json

def update_data(table, pk, sk, sentiment, location):
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    client = dynamodb.Table(table)
    
    client.update_item(
        Key={
            'id_str': pk,
            'timestamp': sk
        },
        UpdateExpression="set sentiment=:s, #ln=:l",
        ConditionExpression='attribute_exists(id_str) AND attribute_exists(#ts)',
        ExpressionAttributeValues={
            ':s': sentiment,
            ':l': location
        },
        ExpressionAttributeNames={
            "#ln": "location",
            "#ts": "timestamp"
        },
        ReturnValues="UPDATED_NEW"
    )

def lambda_handler(event, context):    

    # Stream coming from Kinesis Firehose
    if 'records' in event:     

        output = []
        for record in event['records']:

            try:
                # Kinesis data is base64 encoded so decode here
                payload = base64.b64decode(record['data'])
                print(f'''Decoded payload: {payload}''')
                output_payload = json.loads(payload)

                dataFlatten = flattenData(output_payload)

                dataFlatten['sentiment'] = get_sentiment(dataFlatten['tweet'])
                dataFlatten['location'] = get_location(dataFlatten['location'])

                print(f'''output_payload: {dataFlatten}''')

                output_record = {
                    'recordId': record['recordId'],
                    'result': 'Ok',
                    'data': base64.b64encode(json.dumps(dataFlatten).encode('UTF-8'))
                }

                output.append(output_record)    

            except BaseException as e:
                print(f'''Processing failed with exception: {str(e)}''')
                
                output_record = {
                    'recordId': record['recordId'],
                    'result': 'DeliveryFailed',
                    'data': record['data']
                }

                output.append(output_record)

        return {'records': output}

    # Stream coming from DynamoDB
    if 'Records' in event:

        for record in event['Records']:
            DYNAMO_TABLE = os.environ['TWEET_TABLE']  

            if not DYNAMO_TABLE:
                return "TABLE NOT FOUND"

            if record['eventSource'] == 'aws:dynamodb':

                if record['eventName'] == "INSERT" and 'sentiment' not in record['dynamodb']['NewImage']:
                    print(f'''FROM DynamoDB: {record}''')

                    text = record['dynamodb']['NewImage']['tweet']['S']
                    loc = record['dynamodb']['NewImage']['location']['S'] if 'NULL' not in record['dynamodb']['NewImage']['location'] else None

                    sentiment = get_sentiment(text)
                    location = get_location(loc)

                    primaryKey = record['dynamodb']['Keys']['id_str']['S']
                    sortKey = record['dynamodb']['Keys']['timestamp']['N']

                    try:
                        update_data(DYNAMO_TABLE, primaryKey, int(sortKey), Decimal(sentiment), location)

                    except ClientError as e:
                        print(e.response['Error']['Message'])
                
                else:
                    print(f'''Unused event type record: {record}''')
                    
            else:
                    print(f'''Unused source record: {record}''')

        return 'Successfully processed {} records.'.format(len(event['Records']))

