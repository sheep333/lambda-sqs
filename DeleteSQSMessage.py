import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sqs = boto3.client('sqs')
queue = sqs.Queue("queue_url")


def lambda_handler(event, context):
    try:
        sqs.delete_message(
            QueueUrl="queue_url",
            ReceiptHandle=context['receiptHandle']
        )
    except Exception as e:
        logger.error(e)
        raise e
