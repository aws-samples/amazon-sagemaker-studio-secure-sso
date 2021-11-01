import json
import boto3
import cfnresponse
import time
from botocore.exceptions import ClientError

efs = boto3.client("efs")
cfn = boto3.client("cloudformation")
ec2 = boto3.client("ec2")


def delete_efs(sm_domain_id, vpc_id):
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
            subnets.append(mt["SubnetId"])
        
        while len(efs.describe_mount_targets(FileSystemId=id)["MountTargets"]) > 0:
            print("Wait until mount targets have been deleted")
            time.sleep(5)

        filters = [{"Name":"vpc-id","Values":[vpc_id]},{"Name":"tag:ManagedByAmazonSageMakerResource", 'Values':['*' + sm_domain_id]}]
        security_groups = ec2.describe_security_groups(Filters=filters)["SecurityGroups"]


        print(f"Delete EFS file system {id}")
        efs.delete_file_system(FileSystemId=id)
        
        # Remove all ingress and egress rules
        for sg in security_groups:
            if len(sg["IpPermissionsEgress"]) > 0:
                print(f"revoke egress rule for security group {sg['GroupId']}")
                ec2.revoke_security_group_egress(GroupId=sg["GroupId"], IpPermissions=sg["IpPermissionsEgress"])
            if len(sg["IpPermissions"]) > 0:
                print(f"revoke ingress rule for security group {sg['GroupId']}")
                ec2.revoke_security_group_ingress(GroupId=sg["GroupId"], IpPermissions=sg["IpPermissions"])
        

        # Delete all SageMaker security groups for eth1 (efs)
        # for sg in security_groups:
        #     time.sleep(60)
        #     print(f"delete security group {sg['GroupId']}: {sg['GroupName']}")
        #     ec2.delete_security_group(GroupId=sg["GroupId"])


def lambda_handler(event, context):
    try:
        print(event)
        if event['RequestType'] == 'Delete':
            sm_domain_id = event['ResourceProperties']['DomainId']
            vpc_id = event['ResourceProperties']['vpcId']

            delete_efs(sm_domain_id,vpc_id)
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})    
    except Exception as e:
        print(f"exception: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {}, reason=str(e))
