# My thanks to the open-source community; LLMs brought about a GNU revival
# My thanks to Arize AI in particular; y'all inspired this and other utilities with an awesome observability platform & sessions
# Note: This Lambda has a timeout to ensure it's spun down gracefully; manage your Lambda with Provisioned Concurrency to ensure SQS messages don't get missed

import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from rouge_score import rouge_scorer
import boto3
import time
import json
import os
from botocore.exceptions import ClientError
import datetime
import logging
import random

# Define constants
COSINE_SIMILARITY_THRESHOLD = 0.8
ROUGE_L_THRESHOLD = 0.3
SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/MyQueue'
ALERT_SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/MySecondQueue'
SUSPICIOUS_SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/MyThirdQueue'
SAFE_SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/MyFourthQueue'
S3_BUCKET_NAME = 'my-bucket'
BAD_PROMPTS_FILE_KEY = 'bad_prompts.parquet'
ACCEPTABLE_PROMPTS_FILE_KEY = 'acceptable_prompts.parquet'
RETRY_COUNT = 3  # Define a suitable retry count

# Initialize boto3 clients
s3 = boto3.client('s3')
sqs = boto3.client('sqs')

# Setup logging
logging.basicConfig(level=logging.INFO)

# Load the bad prompts DataFrame from S3
try:
    obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key=BAD_PROMPTS_FILE_KEY)
    bad_prompts_df = pd.read_parquet(obj['Body'])
except ClientError as e:
    logging.error(f'Error loading bad prompts: {e}', exc_info=True)
    raise

# Load the acceptable prompts DataFrame from S3
try:
    obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key=ACCEPTABLE_PROMPTS_FILE_KEY)
    acceptable_prompts_df = pd.read_parquet(obj['Body'])
except ClientError as e:
    logging.error(f'Error loading acceptable prompts: {e}', exc_info=True)
    raise

# Compute Rouge-L scores for the acceptable prompts dataframe once and reuse the result
scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
acceptable_prompts_rougeL_scores = acceptable_prompts_df.apply(lambda row: scorer.score(row['summary'], acceptable_prompts_df['reference_summary'])['rougeL'].fmeasure, axis=1)

# Calculates the baseline vector once; stores in memory for use against each new incoming message
baseline_vectorizer = TfidfVectorizer().fit(baseline_df['text'])
baseline_tfidf_matrix = baseline_vectorizer.transform(baseline_df['text'])

def compute_cosine_similarity(df: pd.DataFrame) -> float:
    vectorizer = TfidfVectorizer(vocabulary=baseline_vectorizer.vocabulary_)
    tfidf_matrix = vectorizer.fit_transform(df['text'])
    cosine_sim = cosine_similarity(tfidf_matrix, baseline_tfidf_matrix)
    return cosine_sim.mean()

def compute_rougeL_scores(df: pd.DataFrame, baseline_df: pd.DataFrame) -> pd.Series:
    scores = df.apply(lambda row: scorer.score(row['summary'], baseline_df['reference_summary'])['rougeL'].fmeasure, axis=1)
    return scores

def send_message_to_sqs(df, queue_url):
    try:
        message = {
            'MessageBody': df.to_json(),
            'QueueUrl': queue_url
        }
        sqs.send_message(**message)
    except Exception as e:
        logging.error(f"Error sending message: {e}", exc_info=True)
        raise

def process_data(df):
    cosine_sim = compute_cosine_similarity(df)
    if cosine_sim >= COSINE_SIMILARITY_THRESHOLD:
        df["rougeL_score"] = compute_rougeL_scores(df, acceptable_prompts_df)
        if df['rougeL_score'].mean() < ROUGE_L_THRESHOLD:
            send_message_to_sqs(df, ALERT_SQS_QUEUE_URL)
        else:
            send_message_to_sqs(df, SUSPICIOUS_SQS_QUEUE_URL)
    else:
        send_message_to_sqs(df, SAFE_SQS_QUEUE_URL)

def receive_message():
    try:
        response = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            AttributeNames=['All'],
            MaxNumberOfMessages=10,
            MessageAttributeNames=['All'],
            VisibilityTimeout=60,
            WaitTimeSeconds=20
        )
    except ClientError as e:
        logging.error(f'Error receiving message: {e}', exc_info=True)
        time.sleep((2 ** RETRY_COUNT) + random.uniform(0, 1))  # Exponential backoff
        RETRY_COUNT -= 1
        if RETRY_COUNT == 0:
            raise
    return response

def lambda_handler(event, context):
    start_time = time.time()

    while True:
        # Check if 10 minutes have passed
        if time.time() - start_time > 600:
            break

        try:
            response = receive_message()

            if 'Messages' in response:
                for message in response['Messages']:
                    receipt_handle = message['ReceiptHandle']

                    try:
                        body = json.loads(message['Body'])
                        df = pd.DataFrame(body)

                        process_data(df)

                        # Delete message after successful processing
                        sqs.delete_message(
                            QueueUrl=SQS_QUEUE_URL,
                            ReceiptHandle=receipt_handle
                        )
                    except Exception as e:
                        logging.error(f'Error processing message: {e}', exc_info=True)
                        raise
            else:
                # No more messages in the queue, terminate the function
                break
        except ClientError as e:
            logging.error(f'Error receiving message: {e}', exc_info=True)
            time.sleep((2 ** RETRY_COUNT) + random.uniform(0, 1))  # Exponential backoff
            RETRY_COUNT -= 1
            if RETRY_COUNT == 0:
                raise
