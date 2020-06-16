import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sqs = boto3.client('sqs')


def lambda_handler(event, context):
    try:
        name = "queue_name"  # TODO:どこかで設定ファイルや環境変数から読み込み？もしくはJSONとして受取り？
        url = sqs.get_queue_url(
            QueueName=name,
        )
        sqs.delete_message(
            QueueUrl=url,
            ReceiptHandle=context['receiptHandle']
        )
    except Exception as e:
        logger.error(e)
        raise e
