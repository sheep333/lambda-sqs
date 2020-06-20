package main

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/aws/aws-lambda-go/ec2"
	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
	"github.com/aws/aws-lambda-go/sqs"
	"github.com/aws/aws-lambda-go/ssm"
	"github.com/aws/aws-sdk-go/aws"
)

// 戻り値はポインタじゃなくてインスタンスの戻り値だけでOKなはず...
func get_instance_ids() (result []*string) {
	svc := ec2.New(session.New())
	// https://docs.aws.amazon.com/sdk-for-go/api/service/ec2/#DescribeInstancesInput
	input := &ec2.DescribeInstancesInput{
		Filters: []*ec2.Filter{
			&ec2.Filter{
				Name: aws.String("tag:Name"),
				Values: []*string{
					aws.String("*sidecar"),
				},
			},
			&ec2.Filter{
				Name:   aws.String("instance-state-name"),
				Values: []*string{aws.String("running")},
			},
		},
	}

	resp, err := svc.DescribeInstances(input)
	if err != nil {
		return err
	}

	// instance
	var instace_ids []*string
	for _, r := range resp.Reservations {
		for _, i := range r.Instances {
			instace_ids = append(instace_ids, *i.InstanceID)
		}
	}

	// DescribeInstancesOutput型を返却
	// https://docs.aws.amazon.com/sdk-for-go/api/service/ec2/#DescribeInstancesOutput
	return instace_ids
}

func exec_ssm_command(instace_ids []*string, message_body string) {
	svc := ssm.New(session.New())
	command := []string{"exec specify command", message_body}
	input := &ssm.SendCommandInput{
		DocumentName: aws.String("Run command for SQS"),
		InstanceIds:  instace_ids,
		Parameters: map[string][]*string{
			"commands": {
				aws.String(strings.Join(command, " ")),
			},
		},
		TimeoutSeconds: aws.Int64(60),
	}
	resp, err := svc.SendCommand(input)

	if err != nil {
		fmt.Println(err.Error())
		return
	}

	return resp.Command.Status
}

func handler(ctx context.Context, sqsEvent events.SQSEvent) error {
	sqs := sqs.New(session.New())
	instance_ids = get_instance_ids()
	for _, message := range sqsEvent.Records {
		resp = exec_ssm_command(instace_ids, message.Body)
		if resp == "Success" {
			input := &sqs.DeleteMessageInput{
				QueueUrl:      aws.String("Queue url"),
				ReceiptHandle: message.ReceiptHandle,
			}
			sqs.DeleteMessage(input)
		} else {
			err := []string{"Command execute error:", resp}
			return errors.New(strings.Join(err))
		}
	}
	return nil
}

func main() {
	lambda.Start(handler)
}
