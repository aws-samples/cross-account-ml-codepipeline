# Create a cross-account machine learning training and deployment environment with AWS Code Pipeline

A continuous integration and continuous delivery (CI/CD) pipeline helps you automate steps in your machine learning (ML) applications such as data ingestion, data preparation, feature engineering, modeling training, and model deployment. A pipeline across multiple AWS accounts improves security, agility, and resilience because an AWS account provides a natural security and access boundary for your AWS resources. This can keep your production environment safe and available for your customers while keeping training separate.

However, setting up the necessary [AWS Identity and Access Management (IAM)](https://aws.amazon.com/iam/) permissions for a multi-account CI/CD pipeline for ML workloads can be difficult. AWS provides solutions such as the [AWS MLOps Framework](https://d1.awsstatic.com/architecture-diagrams/ArchitectureDiagrams/aws-mlops-framework-sol.pdf?did=wp_card&trk=wp_card) and [Amazon SageMaker Pipelines](https://aws.amazon.com/sagemaker/pipelines/) to help customers deploy cross-account ML pipelines quickly. However, customers still want to know how to set up the right cross-accounts IAM roles and trust relationships to create a cross-account pipeline while encrypting their central ML artifact store.

This post is aimed is at helping customers who are familiar with, and prefer [AWS CodePipeline](https://aws.amazon.com/codepipeline/) as their DevOps and automation tool of choice. Although we use machine learning DevOps (MLOps) as an example in this post, you can use this post as a general guide on setting up a cross-account pipeline in CodePipeline incorporating many other AWS services. For MLOps in general, we recommend using SageMaker Pipelines.

## Architecture Overview

We deploy a simple ML pipeline across three AWS accounts. The following in an architecture diagram to represent what you will create. 

![image](https://user-images.githubusercontent.com/42812331/133317827-bee773df-15a1-415e-a331-2e8a8d193a37.png)

For this post, we use three accounts:
* Account A - shared service account
* Account B - training account
* Account C - production account

1.	The shared service account (account A) holds an [AWS CodeCommit](https://aws.amazon.com/codecommit/) repository, an [Amazon Simple Storage Service](https://aws.amazon.com/s3/) (Amazon S3) bucket, an [AWS Key Management Service](https://aws.amazon.com/kms/) (AWS KMS) key, and the CodePipeline. The Amazon S3 bucket contains training data in CSV format and the [model artifacts](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_ModelArtifacts.html).

2.	The pipeline, hosted in the first account, uses [AWS CloudFormation](https://aws.amazon.com/cloudformation/) to deploy an [AWS Step Functions](https://aws.amazon.com/step-functions/?step-functions.sort-by=item.additionalFields.postDateTime&step-functions.sort-order=desc) workflow to train an ML model in the training account (account B). When training completes, the pipeline invokes an [AWS Lambda function](https://aws.amazon.com/lambda/) to create an [Amazon SageMaker](https://aws.amazon.com/sagemaker/) model endpoint in the production account. You can use SageMaker Pipelines as a CI/CD service for ML. However, in this post, we use CodePipeline, which provides flexibility to span across accounts across [AWS Organizations](https://aws.amazon.com/organizations/).

3.	To ensure security of your ML data and artifacts, the bucket policy denies any unencrypted uploads. For example, objects must by encrypted using the KMS key hosted in the shared service account. Additionally, only the CodePipeline and the relevant roles in the training account and the production account have permissions to use the KMS key.

4.	The CodePipeline references CodeCommit as the source provider and the Amazon S3 bucket as the artifact store. When the pipeline detects a change in the CodeCommit repository (for example, new training data is loaded in the Amazon S3), CodePipeline creates or updates the AWS CloudFormation stack in the training account. The stack creates an Step Function state machine. Lastly, CodePipeline invokes the state machine.

5.	The state machine starts a training job in the training account using [SageMaker XGBoost Container](https://github.com/aws/sagemaker-xgboost-container) on the training data in Amazon S3. Once training completes, it outputs the model artifact to the output path. 

6.	CodePipeline waits for manual approval before the final stage of the pipeline to validate training results and ready for production. 

7.	Once approved, Lambda deploys the model to a SageMaker endpoint for production in the production account (account C).


## Deploy AWS CloudFormation Templates

Run the following command to copy the Git repository.
`git clone https://github.com/aws-samples/cross-account-ml-train-deploy-codepipeline`

### In the shared service account (Account A)
1.	Navigate to the [AWS CloudFormation console](https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/).
2.	Select **Create stack**.
3.	Select **Upload a template file** and select the `a-cfn-blog.yml` file. Select **Next**.
4.	Provide a stack name, a CodeCommit repo name, and the three AWS accounts used for the pipeline. Select **Next**.
 
![image](https://user-images.githubusercontent.com/42812331/133318320-a659a219-6ba8-4c15-92fb-56799cf798d3.png)

5.	You can add tags. Otherwise, keep the default stack option configurations and select **Next**.
6.	Acknowledge that AWS CloudFormation might create IAM resources and **Create stack**.

![image](https://user-images.githubusercontent.com/42812331/133318474-e24836f4-e465-4c6f-8f13-b7dfa7429bdf.png)

It will take a few minutes for AWS CloudFormation to deploy the resources. We’ll use the outputs from the stack in A as input for the stacks in B and C. 

### In the training account (Account B)

6.	Select **Create stack** in the AWS CloudFormation console in the training account.
7.	Select **Upload a template file** and choose the `b-cfn-blog.yml file`. Select **Next**.
8.	Give the stack a name and provide the following parameters from the outputs in stack A:
  a.	The role ARN for accessing CodeCommit in the shared service account
  b.	The role ARN of the KMS key
  c.	The shared S3 bucket name
  d.	The AWS account ID for the shared service account

![image](https://user-images.githubusercontent.com/42812331/133318604-5e0e8b34-b3ed-47f8-b2c5-b96162f1976f.png)

9.	Select **Next**.
10.	You can add tags. Otherwise, keep the default stack option configurations and select **Next**.
11.	Acknowledge that AWS CloudFormation might create IAM resources and **Create stack**.

### In the production account (Account C)

12.	Select **Create stack** in the AWS CloudFormation console in the production account.
13.	Select **Upload a template file** and choose `c-cfn-blog.yml file`. Select **Next**.
14.	Provide the KMS key ARN, S3 bucket name, and shared service account ID. Select **Next**.
15.	You can add tags. Otherwise, keep the default stack option configurations and select **Next**.
16.	Acknowledge that AWS CloudFormation might create IAM resources and **Create stack**.

AWS CloudFormation creates the required IAM policies, roles, and trust relationships for your cross-account pipeline. We’ll take the AWS resources and IAM roles created by the templates to populate our pipeline and step function workflow definitions.

## Setting up the pipeline

To run the ML pipeline you must update the pipeline and the Step Functions state machine definition files. You can download the files from the Git repository. Replace the string values within the angle brackets (e.g. ‘<TrainingAccountID >’) with the values created by AWS CloudFormation. 
  
In the shared service account, navigate to the Amazon S3 console and select the Amazon S3 bucket created by AWS CloudFormation. Upload the train.csv file from the Git repository and place in a folder labeled *Data*. Additionally, upload the `train_SF.json` file in the home directory.
  
**Note**: The bucket policy denies any upload actions if not used with the KMS key. As a workaround, remove the bucket policy, upload the files, and re-apply the bucket policy.

  ![image](https://user-images.githubusercontent.com/42812331/133318833-500ed19d-5c54-4149-822b-26e56e7780b6.png)

On to the [CodeCommit page](https://console.aws.amazon.com/codesuite/codecommit/start?region=us-east-1#) select the repository created by AWS CloudFormation. Upload the sf-sm-train-demo.json file into the empty repository. The sf-sm-train-demo.json file should be updated with the values from the AWS CloudFormation template outputs. Provide a name, email, and optional message to the main branch and **Commit changes**.

![image](https://user-images.githubusercontent.com/42812331/133318908-ffa64910-bc76-4547-8401-70e1af2148ea.png)

Now that everything is set up, you can create and deploy the pipeline.
  
## Deploying the pipeline
  
We secured our S3 bucket with the bucket policy and KMS key. Only the CodePipeline service role, and the cross-account roles created by the AWS CloudFormation template in the training and production accounts can use the key. The same applies to the CodeCommit repository. We can run the below command from the shared services account to create the pipeline.
  
`aws codepipeline create-pipeline –cli-input-json file://test_pipeline_v3.json`
  
After a successful response, the custom deploy-cf-train-test stage creates an AWS CloudFormation template in the training account. You can check the CodePipeline status in the [console](https://console.aws.amazon.com/codesuite/codepipeline/home?region=us-east-1).
  
AWS CloudFormation Code deploys a Step Functions state machine to start a model training job by assuming the CodePipeline role in the shared services account. The cross-account role in the training account permits access the S3 bucket, KMS key, CodeCommit repo, and [pass role](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html) Step Functions state machine execution.
 
![image](https://user-images.githubusercontent.com/42812331/133319071-5e98a6aa-9ea3-4c30-ab33-4aed93070fb6.png)

When the state machine successfully runs, the pipeline requests manual approval before the final stage. On the CodePipeline console choose **Review** and **approve** the changes. This moves the pipeline into the final stage of invoking the Lambda function to deploy the model.
  
When the training job completes, the Lambda function in the production account deploys the model endpoint. To do this, the Lambda functions assumes the role in the shared service account to execute the required `PutJobSuccessResult` CodePipeline command.
  
![image](https://user-images.githubusercontent.com/42812331/133319130-7bec7cf0-dc71-4f01-a8f1-9dcf7ea5f7b8.png)

Congratulations! You’ve built the foundation for setting up a cross-account ML pipeline using CodePipeline for training and deployment. You can now see a live SageMaker endpoint in the shared service account created by the Lambda function in the production account.

![image](https://user-images.githubusercontent.com/42812331/133319167-65429c59-c568-48b0-972c-ce0c365ed905.png)

## Conclusion
  
In this blog post, you created a cross-account ML pipeline using CodePipeline, AWS AWS CloudFormation, and Lambda. You set up the necessary IAM policies and roles to enable this cross-account access using a shared services account to hold the ML artifacts in an S3 bucket and a customer-managed KMS key for encryption. You deployed a pipeline where different accounts deployed different stages of the pipeline using AWS CloudFormation to create a Step Functions state machine for model training and Lambda to invoke it.

You can use the steps outlined here to set up cross-account pipelines to fit your workload. For example, you can [use CodePipeline to safely deploy and monitor SageMaker endpoints](https://aws.amazon.com/blogs/machine-learning/safely-deploying-and-monitoring-amazon-sagemaker-endpoints-with-aws-codepipeline-and-aws-codedeploy/). CodePipeline helps you automate steps in your software delivery process to enable agility and productivity for your teams. [Contact your account team](https://aws.amazon.com/contact-us/) to learn how to you can get started today!

  
## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

