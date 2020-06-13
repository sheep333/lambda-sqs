import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.client("ec2")
ssm = boto3.client("ssm")
sqs = boto3.client('sqs')


def lambda_handler(event, context):

    """
    受け取る辞書データ(属性追加も可能)
    {
        "messageId": "2e1424d4-f796-459a-8184-9c92662be6da",
        "receiptHandle": "AQEBzWwaftRI0KuVm4tP+/7q1rGgNqicHq...",
        "body": "Test message.",
        "attributes": {
            "ApproximateReceiveCount": "1",
            "SentTimestamp": "1545082650636",
            "SenderId": "AIDAIENQZJOLO23YVJ4VO",
            "ApproximateFirstReceiveTimestamp": "1545082650649"
        },
        "messageAttributes": {
            "UUID": "xxxxxxxxx"
        },
        "md5OfBody": "e4e68fb7bd0e697a0ae8f1bb342846b3",
        "eventSource": "aws:sqs",
        "eventSourceARN": "arn:aws:sqs:us-east-2:123456789012:my-queue",
        "awsRegion": "us-east-2"
    }
    """

    try:
        for record in event["Records"]:
            message = record["messageAttributes"]

        # all running EC2 instances
        ec2_resp = ec2.describe_instances(Filters=[
            {"Name": f"*sidecar", "Values": ["running"]}])

        # 空配列の場合
        if ec2_resp["Reservations"] is None:
            logger.info("No available instance.")

        # Get InstanceID
        instance = ec2_resp["Reservations"][0]["InstanceId"]
        response = ssm.send_command(
            InstanceIds=instance,
            DocumentName="AWS-RunShellScript",
            Parameters={
                "commands": [
                    f"specify command {message}"
                ],
                "executionTimeout": ["3600"]
            },
        )

        # コマンド実行状況に応じて対応を変更
        # 時間がかかるようならここを非同期的にする仕組み(別Lambdaにしてアプリ側からのpushを受けとる)
        # Lambdaが自動でSQSのメッセージを成功/失敗で場合分して処理してくれる気もするので、そのままResponseを返せばOKかも？
        if response["Command"]["Status"] == "Success":
            name = "queue_name"  # TODO:どこかで設定ファイルや環境変数から読み込み？
            url = sqs.get_queue_url(
                QueueName=name,
            )
            sqs.delete_message(
                QueueUrl=url,
                ReceiptHandle=record["receiptHandle"]
            )

    except Exception as e:
        logger.error(e)
        raise e
