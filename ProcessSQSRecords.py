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
        # バッチサイズを１個にすれば１個ずつ処理できる
        # 複数のメッセージが送信されるバッチにする場合にはメッセージごとの削除がどうなるのかの挙動を確認
        record = event["Records"][0]
        message = record["messageAttributes"]

        # all running EC2 instances
        ec2_resp = ec2.describe_instances(Filters=[
            {"Name": "*sidecar", "Values": ["running"]}])

        # 空配列の場合
        if ec2_resp["Reservations"] is None:
            logger.info("No available instance.")

        # Get InstanceID
        # Lambdaの同時実行を制御しないとDB更新等はデッドロックになりそう
        # LambdaのProvisioned Concurrencyを設定することで初期実行の遅延を制御
        instances = [i["InstanceId"] for r in ec2_resp["Reservations"] for i in r["Instances"]]
 
        response = ssm.send_command(
            InstanceIds=instances,
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
        if response["Command"]["Status"] == "Success":
            logger.info(response)
        else:
            raise RuntimeError

    except Exception as e:
        logger.error(e)
        raise e
