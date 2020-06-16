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
    "Records": [
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
    ]
    """

    try:
        # 複数のメッセージをバッチで受信
        record = event["Records"]

        # all running EC2 instances
        ec2_resp = ec2.describe_instances(Filters=[
            {"Name": "*sidecar", "Values": ["running"]}])

        # 空dictの場合
        if ec2_resp["Reservations"] is None:
            logger.info("No available instance.")

        # インスタンスIDを取得
        # 関数実行のタイムアウトの6倍の可視性タイムアウト設定が必要
        # https://docs.aws.amazon.com/ja_jp/lambda/latest/dg/with-sqs.html#events-sqs-eventsource
        instances = [i["InstanceId"] for r in ec2_resp["Reservations"] for i in r["Instances"]]
        for message in record:
            response = ssm.send_command(
                InstanceIds=instances,
                DocumentName="AWS-RunShellScript",
                Parameters={
                    "commands": [
                        f"specify command {message}"
                    ],
                    "executionTimeout": ["60"]
                },
            )
            if response["Command"]["Status"] == "Success":
                # 成功した場合は個別でメッセージを削除する
                logger.info(response)
                sqs.delete_message(
                    QueueUrl="queue_url",
                    ReceiptHandle=message['receiptHandle']
                )
            else:
                # 成功以外の場合はバッチごとキューに積み直し
                # 成功したメッセージは消えているはず...
                raise RuntimeError

        # コマンド実行状況に応じて対応を変更
        # 時間がかかるようならここを非同期的にする仕組み(別Lambdaにしてアプリ側からのpushを受けとる)
        # Lambdaが自動でSQSのメッセージを成功/失敗で場合分して処理してくれる気もするので、そのままResponseを返せばOKかも？
        """
        Pending: The command has not been sent to any instances.
        In Progress: The command has been sent to at least one instance but has not reached a final state on all instances.
        Success: The command successfully ran on all invocations. This is a terminal state.
        Delivery Timed Out: The value of MaxErrors or more command invocations shows a status of Delivery Timed Out. This is a terminal state.
        Execution Timed Out: The value of MaxErrors or more command invocations shows a status of Execution Timed Out. This is a terminal state.
        Failed: The value of MaxErrors or more command invocations shows a status of Failed. This is a terminal state.
        Incomplete: The command was attempted on all instances and one or more invocations does not have a value of Success but not enough invocations failed for the status to be Failed. This is a terminal state.
        Canceled: The command was terminated before it was completed. This is a terminal state.
        Rate Exceeded: The number of instances targeted by the command exceeded the account limit for pending invocations. The system has canceled the command before running it on any instance. This is a terminal state.
        """

    except Exception as e:
        logger.error(e)
        raise e
