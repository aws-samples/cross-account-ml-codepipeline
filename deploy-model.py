import json
import boto3
import os
import logging
# pipeline = boto3.client('codepipeline')

def lambda_handler(event, context):
    # TODO implement
    print(event)
    
    
    print(event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters'])
    
    STS_SESSION = get_sts_session(event, \
    event['CodePipeline.job']['accountId'], \
    event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters'])
    iam = STS_SESSION.client('iam')
    codepipeline = STS_SESSION.client('codepipeline')
    codepipeline.put_job_success_result(
        jobId=event['CodePipeline.job']['id']
    )
    return 0



def put_job_success(event):
    
    print("[SUCCESS]Endpoint Deployed")
    print(event['message'])
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])

def put_job_failure(event):  
    print('[ERROR]Putting job failure')
    print(event['message'])
    code_pipeline.put_job_success_result(jobId=event['CodePipeline.job']['id'])
    
def get_sts_session(event, account, rolename):
    sts = boto3.client("sts")
    RoleArn = str("arn:aws:iam::" + account + ":role/" + rolename)
    print(RoleArn)
    response = sts.assume_role(
        RoleArn=RoleArn,
        RoleSessionName='SecurityManageAccountPermissions',
        DurationSeconds=900)
    sts_session = boto3.Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'],
        aws_secret_access_key=response['Credentials']['SecretAccessKey'],
        aws_session_token=response['Credentials']['SessionToken'],
        region_name=os.environ['AWS_REGION'],
        botocore_session=None,
        profile_name=None)
    return (sts_session)