# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import cfnresponse
import time
from botocore.exceptions import ClientError

efs = boto3.client("efs")
cfn = boto3.client("cloudformation")
ec2 = boto3.client("ec2")


def delete_efs(sm_domain_id):
    subnets = []

    # Get EFS which belongs to SageMaker (based on a tag)
    print(f"Get EFS file system id(s) for SageMaker domain id {sm_domain_id}")
    for id in [
        fs["FileSystemId"] for fs in efs.describe_file_systems()["FileSystems"] 
            if fs.get("Tags") and [t["Value"] for t in fs["Tags"] if t["Key"]=="ManagedByAmazonSageMakerResource"][0].split("/")[-1] == sm_domain_id
        ]:
        
        print(f"Delete mount targets for EFS file system id: {id}")
        for mt in efs.describe_mount_targets(FileSystemId=id)["MountTargets"]:
            efs.delete_mount_target(MountTargetId=mt["MountTargetId"])
            vpc_id = mt['VpcId']
            subnets.append(mt["SubnetId"])
        
        while len(efs.describe_mount_targets(FileSystemId=id)["MountTargets"]) > 0:
            print("Wait until mount targets have been deleted")
            time.sleep(5)

        filters = [{"Name":"vpc-id","Values":[vpc_id]},{"Name":"tag:ManagedByAmazonSageMakerResource", "Values":["*"+ sm_domain_id]}]
        security_groups = ec2.describe_security_groups(Filters=filters)["SecurityGroups"]
        
        group_ids = []
        # Remove all ingress and egress rules
        for sg in security_groups:
            if len(sg["IpPermissionsEgress"]) > 0:
                print(f"revoke egress rule for security group {sg['GroupId']}")
                ec2.revoke_security_group_egress(GroupId=sg["GroupId"], IpPermissions=sg["IpPermissionsEgress"])
            if len(sg["IpPermissions"]) > 0:
                print(f"revoke ingress rule for security group {sg['GroupId']}")
                ec2.revoke_security_group_ingress(GroupId=sg["GroupId"], IpPermissions=sg["IpPermissions"])
            group_ids.append(sg["GroupId"])


        # Remove Security assignment from ENIs
        default_group_id = [ec2.describe_security_groups(Filters=[{"Name":"group-name","Values":['default']},{"Name":"vpc-id","Values":[vpc_id]}])['SecurityGroups'][0]["GroupId"]]
        enis = ec2.describe_network_interfaces(Filters=[{"Name":"group-id","Values":group_ids}])['NetworkInterfaces']

        for eni in enis:            
            eni_id = eni["NetworkInterfaceId"]
            print(f"Assigning default security group to ENI {eni_id}")
            ec2.modify_network_interface_attribute(Groups=default_group_id,NetworkInterfaceId=eni_id)

        # Delete all SageMaker security groups (efs)
        for sg in security_groups:
            print(f"delete security group {sg['GroupId']}: {sg['GroupName']}")
            ec2.delete_security_group(GroupId=sg["GroupId"])

        print(f"Delete EFS file system {id}")
        efs.delete_file_system(FileSystemId=id)            
    

def lambda_handler(event, context):
    print('Invokation')
    print(event)
    try:
        if event['RequestType'] == 'Delete':
            sm_domain_id = event['ResourceProperties']['DomainId']
            delete_efs(sm_domain_id)

        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})    
    except Exception as e:
        print(f"exception: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {}, reason=str(e))
