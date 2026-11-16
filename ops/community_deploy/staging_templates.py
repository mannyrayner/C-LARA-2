"""Render reviewable, isolated CloudFormation templates; never calls AWS."""
import json


def ref(name):
    return {'Ref': name}


def sub(value, values=None):
    return {'Fn::Sub': value if values is None else [value, values]}


def attr(name, field):
    return {'Fn::GetAtt': [name, field]}


def imported(field):
    return {'Fn::ImportValue': sub('${HostStackName}-' + field)}


def allow(actions, resources):
    return {'Effect': 'Allow', 'Action': actions, 'Resource': resources}


def assume(service):
    return {'Version': '2012-10-17', 'Statement': [{'Effect':'Allow',
        'Principal':{'Service':service}, 'Action':'sts:AssumeRole'}]}


def host_template(user_data):
    resources = {
        'Vpc': {'Type':'AWS::EC2::VPC','Properties':{'CidrBlock':'10.77.0.0/24',
            'EnableDnsSupport':True,'EnableDnsHostnames':True}},
        'Gateway': {'Type':'AWS::EC2::InternetGateway'},
        'GatewayAttachment': {'Type':'AWS::EC2::VPCGatewayAttachment','Properties':{
            'VpcId':ref('Vpc'),'InternetGatewayId':ref('Gateway')}},
        'Subnet': {'Type':'AWS::EC2::Subnet','Properties':{'VpcId':ref('Vpc'),
            'CidrBlock':'10.77.0.0/24','MapPublicIpOnLaunch':False}},
        'RouteTable': {'Type':'AWS::EC2::RouteTable','Properties':{'VpcId':ref('Vpc')}},
        'Route': {'Type':'AWS::EC2::Route','DependsOn':'GatewayAttachment','Properties':{
            'RouteTableId':ref('RouteTable'),'DestinationCidrBlock':'0.0.0.0/0','GatewayId':ref('Gateway')}},
        'Association': {'Type':'AWS::EC2::SubnetRouteTableAssociation','Properties':{
            'SubnetId':ref('Subnet'),'RouteTableId':ref('RouteTable')}},
        'Group': {'Type':'AWS::EC2::SecurityGroup','Properties':{'GroupDescription':'Isolated staging HTTPS',
            'VpcId':ref('Vpc'), 'SecurityGroupIngress':[
                {'IpProtocol':'tcp','FromPort':port,'ToPort':port,'CidrIp':'0.0.0.0/0'} for port in (80,443)],
            'SecurityGroupEgress':[
                {'IpProtocol':'tcp','FromPort':port,'ToPort':port,'CidrIp':'0.0.0.0/0'} for port in (80,443)] +
                [{'IpProtocol':protocol,'FromPort':53,'ToPort':53,'CidrIp':'10.77.0.2/32'}
                 for protocol in ('tcp','udp')]}},
        'HostRole': {'Type':'AWS::IAM::Role','Properties':{'AssumeRolePolicyDocument':assume('ec2.amazonaws.com'),
            'Policies':[{'PolicyName':'staging-bootstrap','PolicyDocument':{'Version':'2012-10-17',
                'Statement':[
                    allow('ssm:UpdateInstanceInformation','*'),
                    allow(['ssmmessages:CreateControlChannel','ssmmessages:CreateDataChannel',
                           'ssmmessages:OpenControlChannel','ssmmessages:OpenDataChannel'],'*'),
                    allow(['ssm:GetDocument','ssm:DescribeDocument'],sub('arn:${AWS::Partition}:ssm:${AWS::Region}::document/AWS-RunShellScript')),
                    allow('s3:GetObject',sub('arn:${AWS::Partition}:s3:::${ArtifactBucket}/staging/bootstrap/*'))
                ]}}]}},
        'Profile': {'Type':'AWS::IAM::InstanceProfile','Properties':{'Roles':[ref('HostRole')]}},
        'Host': {'Type':'AWS::EC2::Instance','DependsOn':['Route','Association'],
            'DeletionPolicy':'Retain','UpdateReplacePolicy':'Retain','Properties':{
                'ImageId':ref('AmiId'),'InstanceType':'t3.small','SubnetId':ref('Subnet'),
                'SecurityGroupIds':[ref('Group')],'IamInstanceProfile':ref('Profile'),
                'CreditSpecification':{'CPUCredits':'standard'},'InstanceInitiatedShutdownBehavior':'stop',
                'PropagateTagsToVolumeOnCreation':True,
                'DisableApiTermination':True,'MetadataOptions':{'HttpTokens':'required','HttpPutResponseHopLimit':1},
                'BlockDeviceMappings':[{'DeviceName':'/dev/sda1','Ebs':{'VolumeType':'gp3',
                    'VolumeSize':24,'Encrypted':True,'DeleteOnTermination':False}}],
                'UserData':{'Fn::Base64':user_data},
                'Tags':[{'Key':'Name','Value':'clara-community-staging'},
                        {'Key':'ClaraEnvironment','Value':'staging'}]}},
        'Address': {'Type':'AWS::EC2::EIP','DependsOn':'GatewayAttachment','DeletionPolicy':'Retain',
                    'UpdateReplacePolicy':'Retain','Properties':{'Domain':'vpc'}},
        'AddressAssociation': {'Type':'AWS::EC2::EIPAssociation','Properties':{
            'AllocationId':attr('Address','AllocationId'),'InstanceId':ref('Host')}}}
    outputs = {'InstanceId':ref('Host'),'HostRoleName':ref('HostRole'),
               'HostProfileArn':attr('Profile','Arn'),'PublicIp':ref('Address')}
    return {'AWSTemplateFormatVersion':'2010-09-09',
        'Description':'Normally stopped isolated staging host; initial OS preparation is bounded.',
        'Parameters':{'AmiId':{'Type':'AWS::EC2::Image::Id'},'ArtifactBucket':{'Type':'String',
                      'AllowedPattern':'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]'}},
        'Resources':resources,'Outputs':{name:{'Value':value,
            'Export':{'Name':sub('${AWS::StackName}-'+name)}} for name,value in outputs.items()}}


def runtime_template(ssm_document):
    arn = 'arn:${AWS::Partition}'
    fn = arn+':lambda:${AWS::Region}:${AWS::AccountId}:function:${FunctionName}'
    instance = sub(arn+':ec2:${AWS::Region}:${AWS::AccountId}:instance/${InstanceId}',
                   {'InstanceId':imported('InstanceId')})
    state = sub(arn+':s3:::${StateBucket}/staging/lifecycle.json')
    fixture = sub(arn+':s3:::${StateBucket}/staging/fixture.json')
    document = sub(arn+':ssm:${AWS::Region}:${AWS::AccountId}:document/CLARA-DeployStaging')
    schedule_arn = arn+':scheduler:${AWS::Region}:${AWS::AccountId}:schedule/${ScheduleGroupName}/${ScheduleName}'
    config = {
        'live_enabled':'${LiveBoolean}','region':'${AWS::Region}','instance_id':'${InstanceId}',
        'policy_revision':'${PolicyRevision}','guard_revision':'${GuardRevision}',
        'guard_sha256':'${GuardSha256}','max_lease_minutes':120,'monthly_seconds':288000,
        'state_bucket':'${StateBucket}','state_key':'staging/lifecycle.json',
        'ssm_document_version':'1','hostname':'${Hostname}',
        'health_url':'https://${Hostname}/community-dictionaries/deployment-health/',
        'function_name':'${FunctionName}','live_alias_arn':fn+':live','watchdog_alias_arn':fn+':watchdog',
        'schedule_name':'${ScheduleName}','schedule_group':'${ScheduleGroupName}',
        'credential_secret_arn':'${Credentials}','control_repository':'mannyrayner/clara-staging-control',
        'control_repository_id':'${ControlRepositoryId}','allowed_sender_ids':'${AllowedSenderIds}'}
    config_json = json.dumps(config,separators=(',',':')).replace('"${LiveBoolean}"','${LiveBoolean}')
    config_json = config_json.replace('"${ControlRepositoryId}"','${ControlRepositoryId}')
    config_json = config_json.replace('"${AllowedSenderIds}"','[${AllowedSenderIds}]')
    resources = {
        'StateBucket': {'Type':'AWS::S3::Bucket','DeletionPolicy':'Retain','UpdateReplacePolicy':'Retain',
            'Properties':{'BucketEncryption':{'ServerSideEncryptionConfiguration':[
                {'ServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]},
                'PublicAccessBlockConfiguration':{k:True for k in
                    ('BlockPublicAcls','BlockPublicPolicy','IgnorePublicAcls','RestrictPublicBuckets')},
                'VersioningConfiguration':{'Status':'Enabled'},
                'LifecycleConfiguration':{'Rules':[{'Id':'BoundedEvidence','Status':'Enabled',
                    'Prefix':'evidence/','ExpirationInDays':30,'NoncurrentVersionExpiration':{'NoncurrentDays':7}},
                    {'Id':'BoundedStateHistory','Status':'Enabled','Prefix':'staging/',
                     'NoncurrentVersionExpiration':{'NoncurrentDays':7}}]}}},
        'Credentials': {'Type':'AWS::SecretsManager::Secret','DeletionPolicy':'Retain',
            'UpdateReplacePolicy':'Retain',
            'Properties':{'Description':'Staging-only HTTP and synthetic browser fixture seed',
                'GenerateSecretString':{'SecretStringTemplate':'{}','GenerateStringKey':'seed',
                    'PasswordLength':40,'ExcludePunctuation':True}}},
        'LogGroup': {'Type':'AWS::Logs::LogGroup','Properties':{
            'LogGroupName':sub('/aws/lambda/${FunctionName}'),'RetentionInDays':14}},
        'CoordinatorRole': {'Type':'AWS::IAM::Role','Properties':{
            'AssumeRolePolicyDocument':assume('lambda.amazonaws.com'),
            'Policies':[{'PolicyName':'fixed-staging-coordinator','PolicyDocument':{
                'Version':'2012-10-17','Statement':[
                    allow(['ec2:StartInstances','ec2:StopInstances'],instance),
                    allow(['ec2:DescribeInstances','ec2:DescribeInstanceAttribute'],'*'),
                    allow('ssm:SendCommand',[document,instance]),allow('ssm:GetCommandInvocation','*'),
                    allow(['s3:GetObject','s3:PutObject'],state),
                    allow(['lambda:GetFunctionConcurrency','lambda:GetAlias'],[sub(fn),sub(fn+':live'),sub(fn+':watchdog')]),
                    allow('scheduler:GetSchedule',sub(schedule_arn)),
                    allow('secretsmanager:GetSecretValue',ref('Credentials')),
                    allow(['logs:CreateLogStream','logs:PutLogEvents'],sub(arn+':logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/${FunctionName}:*'))
                ]}}]}},
        'Function': {'Type':'AWS::Lambda::Function','DependsOn':'LogGroup','Properties':{
            'FunctionName':ref('FunctionName'),'Runtime':'python3.12','Handler':'staging_runtime_app.handler',
            'MemorySize':256,'Timeout':90,'ReservedConcurrentExecutions':1,
            'Role':attr('CoordinatorRole','Arn'),'Code':{'S3Bucket':ref('ArtifactBucket'),
                'S3Key':ref('RuntimeCodeKey')},
            'Environment':{'Variables':{'CLARA_STAGING_CONFIG_JSON':sub(config_json,{
                'InstanceId':imported('InstanceId'),
                'LiveBoolean':{'Fn::If':['IsLive','true','false']}})}}}},
        'Version': {'Type':'AWS::Lambda::Version','Properties':{'FunctionName':ref('Function'),
            'CodeSha256':ref('RuntimeZipSha256'),
            'Description':sub('${PolicyRevision}:${GuardRevision}:${EnableLive}')}},
        'LiveAlias': {'Type':'AWS::Lambda::Alias','Properties':{'FunctionName':ref('Function'),
            'FunctionVersion':attr('Version','Version'),'Name':'live'}},
        'WatchdogAlias': {'Type':'AWS::Lambda::Alias','Properties':{'FunctionName':ref('Function'),
            'FunctionVersion':attr('Version','Version'),'Name':'watchdog'}},
        'WatchdogRetries': {'Type':'AWS::Lambda::EventInvokeConfig','DependsOn':'WatchdogAlias',
            'Properties':{'FunctionName':ref('Function'),'Qualifier':'watchdog',
                'MaximumEventAgeInSeconds':60,'MaximumRetryAttempts':0}},
        'DeployDocument': {'Type':'AWS::SSM::Document','Properties':{'Name':'CLARA-DeployStaging',
            'DocumentType':'Command','DocumentFormat':'JSON','Content':ssm_document,'UpdateMethod':'NewVersion'}},
        'ScheduleGroup': {'Type':'AWS::Scheduler::ScheduleGroup','Properties':{'Name':ref('ScheduleGroupName')}},
        'SchedulerRole': {'Type':'AWS::IAM::Role','Properties':{
            'AssumeRolePolicyDocument':{'Version':'2012-10-17','Statement':[{
                'Effect':'Allow','Principal':{'Service':'scheduler.amazonaws.com'},'Action':'sts:AssumeRole',
                'Condition':{'StringEquals':{'aws:SourceAccount':ref('AWS::AccountId')},
                    'ArnEquals':{'aws:SourceArn':sub(arn+':scheduler:${AWS::Region}:${AWS::AccountId}:schedule-group/${ScheduleGroupName}')}}}]},
            'Policies':[{'PolicyName':'watchdog-only','PolicyDocument':{'Version':'2012-10-17',
                'Statement':[allow('lambda:InvokeFunction',ref('WatchdogAlias'))]}}]}},
        'Schedule': {'Type':'AWS::Scheduler::Schedule','Properties':{'Name':ref('ScheduleName'),
            'GroupName':ref('ScheduleGroup'),'ScheduleExpression':'rate(1 minute)',
            'State':{'Fn::If':['IsLive','ENABLED','DISABLED']},'FlexibleTimeWindow':{'Mode':'OFF'},
            'Target':{'Arn':ref('WatchdogAlias'),'RoleArn':attr('SchedulerRole','Arn'),
                'Input':'{"action":"tick"}',
                'RetryPolicy':{'MaximumEventAgeInSeconds':60,'MaximumRetryAttempts':0}}}},
        'HostPermissions': {'Type':'AWS::IAM::Policy','Properties':{'PolicyName':'own-staging-resources',
            'Roles':[imported('HostRoleName')],'PolicyDocument':{'Version':'2012-10-17','Statement':[
                allow('s3:GetObject',state),allow('s3:PutObject',[fixture,
                    sub(arn+':s3:::${StateBucket}/staging/bootstrap-receipt.json')]),
                allow('secretsmanager:GetSecretValue',ref('Credentials')),
                allow(['ssm:GetDocument','ssm:DescribeDocument'],document)]}}},
        'RequesterRole': {'Type':'AWS::IAM::Role','Properties':{'MaxSessionDuration':3600,
            'AssumeRolePolicyDocument':{'Version':'2012-10-17','Statement':[{'Effect':'Allow',
                'Principal':{'Federated':sub(arn+':iam::${AWS::AccountId}:oidc-provider/token.actions.githubusercontent.com')},
                'Action':'sts:AssumeRoleWithWebIdentity','Condition':{'StringEquals':{
                    'token.actions.githubusercontent.com:aud':'sts.amazonaws.com',
                    'token.actions.githubusercontent.com:sub':'repo:mannyrayner/clara-staging-control:ref:refs/heads/main'}}}]},
            'Policies':[{'PolicyName':'bounded-staging-request','PolicyDocument':{'Version':'2012-10-17',
                'Statement':[allow('lambda:InvokeFunction',ref('LiveAlias')),
                    allow('secretsmanager:GetSecretValue',ref('Credentials')),allow('s3:GetObject',fixture),
                    allow('s3:PutObject',sub(arn+':s3:::${StateBucket}/evidence/*'))]}}]}}
    }
    resources.update({
        'Alerts':{'Type':'AWS::SNS::Topic','Properties':{'Subscription':[
            {'Protocol':'email','Endpoint':ref('AdminEmail')}] }},
        'AlertsPolicy':{'Type':'AWS::SNS::TopicPolicy','Properties':{'Topics':[ref('Alerts')],
            'PolicyDocument':{'Version':'2012-10-17','Statement':[{'Effect':'Allow',
                'Principal':{'Service':'cloudwatch.amazonaws.com'},'Action':'sns:Publish',
                'Resource':ref('Alerts'),'Condition':{'StringEquals':{'aws:SourceAccount':ref('AWS::AccountId')},
                    'ArnLike':{'aws:SourceArn':sub(arn+':cloudwatch:${AWS::Region}:${AWS::AccountId}:alarm:clara-community-staging-*')}}}]}}},
        'WatchdogFailureAlarm':{'Type':'AWS::CloudWatch::Alarm','Condition':'IsLive','Properties':{
            'AlarmName':'clara-community-staging-watchdog-failure','Namespace':'AWS/Lambda',
            'MetricName':'Errors','Dimensions':[{'Name':'FunctionName','Value':ref('FunctionName')}],
            'Statistic':'Sum','Period':60,'EvaluationPeriods':1,'Threshold':1,
            'ComparisonOperator':'GreaterThanOrEqualToThreshold','TreatMissingData':'notBreaching',
            'AlarmActions':[ref('Alerts')]}},
        'WatchdogMissingAlarm':{'Type':'AWS::CloudWatch::Alarm','Condition':'IsLive','Properties':{
            'AlarmName':'clara-community-staging-watchdog-missing','Namespace':'AWS/Scheduler',
            'MetricName':'InvocationAttemptCount','Dimensions':[{'Name':'ScheduleGroup','Value':ref('ScheduleGroupName')}],
            'Statistic':'Sum','Period':120,'EvaluationPeriods':2,'Threshold':1,
            'ComparisonOperator':'LessThanThreshold','TreatMissingData':'breaching','AlarmActions':[ref('Alerts')]}},
        'Budget':{'Type':'AWS::Budgets::Budget','Properties':{'Budget':{'BudgetName':'clara-community-staging',
            'BudgetType':'COST','TimeUnit':'MONTHLY','BudgetLimit':{'Amount':10,'Unit':'USD'},
            'CostFilters':{'TagKeyValue':['user:ClaraEnvironment$staging']}},
            'NotificationsWithSubscribers':[{'Notification':{'NotificationType':'ACTUAL',
                'ComparisonOperator':'GREATER_THAN','Threshold':threshold,'ThresholdType':'PERCENTAGE'},
                'Subscribers':[{'SubscriptionType':'EMAIL','Address':ref('AdminEmail')}]}
                 for threshold in (80,100)]}}
    })
    parameters = {
        'HostStackName':{'Type':'String','Default':'clara-community-staging-host'},
        'ArtifactBucket':{'Type':'String','AllowedPattern':'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]'},
        'RuntimeZipSha256':{'Type':'String','AllowedPattern':'[A-Za-z0-9+/]{43}='},
        'RuntimeCodeKey':{'Type':'String','AllowedPattern':r'staging/bootstrap/runtime-[0-9a-f]{64}\.zip'},
        'GuardRevision':{'Type':'String','AllowedPattern':'[0-9a-f]{40}'},
        'PolicyRevision':{'Type':'String','AllowedPattern':'[0-9a-f]{40}'},
        'GuardSha256':{'Type':'String','AllowedPattern':'[0-9a-f]{64}'},
        'Hostname':{'Type':'String','Default':'c-lara-2-staging.c-lara.org','AllowedPattern':'[a-z0-9][a-z0-9.-]+'},
        'FunctionName':{'Type':'String','Default':'clara-community-staging-coordinator','AllowedPattern':'[a-zA-Z0-9-_]+'},
        'ScheduleName':{'Type':'String','Default':'clara-community-staging-expiry'},
        'ScheduleGroupName':{'Type':'String','Default':'clara-community-staging'},
        'ControlRepositoryId':{'Type':'String','AllowedPattern':'[1-9][0-9]+'},
        'AllowedSenderIds':{'Type':'String','AllowedPattern':'[1-9][0-9]+(,[1-9][0-9]+)*'},
        'AdminEmail':{'Type':'String','AllowedPattern':'[^\\s@]+@[^\\s@]+\\.[^\\s@]+'},
        'EnableLive':{'Type':'String','AllowedValues':['false','true'],'Default':'false'}}
    return {'AWSTemplateFormatVersion':'2010-09-09','Description':'Disabled-by-default staging coordinator and independent watchdog.',
        'Parameters':parameters,'Conditions':{'IsLive':{'Fn::Equals':[ref('EnableLive'),'true']}},
        'Resources':resources,'Outputs':{'StateBucket':{'Value':ref('StateBucket')},
            'CredentialSecretArn':{'Value':ref('Credentials')},'RequesterRoleArn':{'Value':attr('RequesterRole','Arn')},
            'LiveAliasArn':{'Value':ref('LiveAlias')},'WatchdogAliasArn':{'Value':ref('WatchdogAlias')}}}
