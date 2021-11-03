# amazon-sagemaker-studio-secure-sso

This solution provides a way to deploy SageMaker Studio in a private and secure environment. The solution integrates with a [Custom SAML 2.0 Application](https://docs.aws.amazon.com/singlesignon/latest/userguide/samlapps.html) as the mechanism to trigger the authentication to Amazon SageMaker Studio. It requires that the Custom SAML application is configured with the Amazon API Gateway endpoint URL as its ACS (Assertion Consumer Service) and needs mapping attributes containing the AWS SSO User ID as well as the Amazon SageMaker Domain Domain ID. 
The Amazon API Gateway is configured to trigger an AWS Lambda function that parses the SAML response to extract the Domain ID and User ID and use it to generate the SageMaker Studio Presigned URL and eventually perform redirection to log the user in Amazon SageMaker Studio. The control of the environment that SageMaker Studio users are able to login from is done by an AWS IAM Policy that includes a condition to allow the generation of the predefined URL only from specific(s) IPs, which is attached to the AWS Lambda function.

The deployment procedure assumes that [AWS Single Sign On](https://docs.aws.amazon.com/singlesignon/latest/userguide/what-is.html) has been enabled and configured for the [AWS Organization](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_introduction.html) where the solution will be deployed.

## Deploy the Amazon Sagemaker Studio Secure with Single Sign On solution

* Retrieve the AWS SSO User ID - can be done through the console or using the following command
```sh
aws identitystore list-users --identity-store-id '<Identity Store ID>' --filter AttributePath='UserName',AttributeValue='user@company.com'
```
* Build and deploy the SAM Application with the following command
```sh
sam build && sam deploy --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND --stack-name sagemaker-secure-sso --guided
```
* Set the parameter **UserProfileName** to the User ID retreived in the first step
* Go to the AWS SSO Console and create a new [Custom SAML 2.0 Application](https://docs.aws.amazon.com/singlesignon/latest/userguide/samlapps.html)
* Name the Custom SAML 2.0 Application ```SageMaker Secure Demo```
* Set the Application ACS URL to the URL provided in the **SAMLBackEndApi** Key SAM Output
* Save the application and re-open then go under Attribute mappings
* Set the Subject to **email** and format **emailAddress**
* Add a new attribute named **domain-id** and set the value to the Key SAM Output **SageMakerStudioDomainId**
* Add a new attribute named **username** and set the value to **${user:AD_GUID}**

![image info](./img/SSO_App_Config.png)

## How to test the solution

The solution deploys 3 EC2 instances for demonstrating the solution. 

* 1 EC2 Windows in a private subnet that is able to access Amazon SageMaker Studio  (think your onpremise secured environment)
* 1 EC2 Linux in the public subnet acting as Bastion host used to establish an SSH tunnel into the EC2 Windows on the private network
* 1 EC2 Windows in a public subnet to demonstrate that SageMaker Studio can't be accessed from unauthorised subnets - IP Available as the **SageMakerWindowsBastionHost** Key SAM Output 

Note that the password for the Windows EC2 instances is provided in the output under the **SageMakerWindowsPassword** key value. To change it, run the following command in a Windows Command prompt at the first login.

```batch
net user Administrator "NewPassword"
```

### Test to Access Amazon SageMaker Studio from authorised network

* To access the EC2 Windows on the private network, run the command provided as the value of the SAM output Key **TunnelCommand**, make sure that the public key of the KeyPair specified in the parameter is the directory where the SSH tunnel command is run from.
* Open a new RDP connection on localhost and port 3389, open the Firefox web browser from the Desktop and navigate and login to the AWS Single Sign On portal using the credentials associated with the User ID that was specified as the **UserProfileName** parameter.
* Click the ```SageMaker Secure Demo``` SSO Application from the AWS Single Sign On portal

**Expected Result**: User is logged in to Amazon SageMaker Studio

### Test to Access Amazon SageMaker Studio from unauthorised network

* Open a new RDP connection on the IP provided in the **SageMakerWindowsBastionHost** SAML output and port 3389, open the Firefox web browser from the Desktop and navigate and login to the AWS Single Sign On portal using the credentials associated with the User ID that was specified as the **UserProfileName** parameter.
* Click the ```SageMaker Secure Demo``` SSO Application from the AWS Single Sign On portal

**Expected Result**: User receives an unthorised access message

In order to centrally prevent access to SageMaker Studio for users within the console we recommend to implement the following [Service Control Policy](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html) and attach it to the account where SageMaker Studio is or can be deployed. 
Make sure to replace the ***<AuthorizedPrivateSubnet>*** with the source IP CDIR block you want to allow SageMaker Studio access from.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "sagemaker:*"
      ],
      "Resource": "*",
      "Effect": "Allow"
    },
    {
      "Condition": {
        "NotIpAddress": {
          "aws:VpcSourceIp": "<AuthorizedPrivateSubnet>"
        }
      },
      "Action": [
        "sagemaker:CreatePresignedDomainUrl"
      ],
      "Resource": "*",
      "Effect": "Deny"
    }
  ]
}
```

## Cleanup

To delete the solution application that you created, use the AWS CLI. Assuming you used the default project name for the stack name, you can run the following:

```bash
aws cloudformation delete-stack --stack-name sagemaker-secure-sso
```