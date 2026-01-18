import { CfnOutput, CfnParameter, Duration, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import { Construct } from 'constructs';

export class InfraStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const stage = (this.node.tryGetContext('stage') as string | undefined) ?? 'dev';

    const dbName = new CfnParameter(this, 'DbName', {
      type: 'String',
      description: 'Default database name.',
      default: (this.node.tryGetContext('dbName') as string | undefined) ?? `saihai_${stage}`,
    });

    const allowedCidr = new CfnParameter(this, 'DbAllowedCidr', {
      type: 'String',
      description: 'CIDR allowed to connect to the Aurora PostgreSQL writer endpoint (tcp/5432).',
      default: '203.0.113.0/32',
    });

    const vpc = new ec2.Vpc(this, 'SaihaiVpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        { name: `${stage}-public`, subnetType: ec2.SubnetType.PUBLIC },
        { name: `${stage}-isolated`, subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      ],
    });

    const dbSecurityGroup = new ec2.SecurityGroup(this, 'SaihaiDbSecurityGroup', {
      vpc,
      description: 'Aurora PostgreSQL access',
      allowAllOutbound: true,
    });
    dbSecurityGroup.addIngressRule(
      ec2.Peer.ipv4(allowedCidr.valueAsString),
      ec2.Port.tcp(5432),
      'Allow PostgreSQL from allowed CIDR'
    );

    const cluster = new rds.DatabaseCluster(this, 'SaihaiAuroraPostgres', {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_15_4,
      }),
      writer: rds.ClusterInstance.provisioned('writer', {
        instanceType: ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MEDIUM),
        publiclyAccessible: true,
      }),
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      securityGroups: [dbSecurityGroup],
      defaultDatabaseName: dbName.valueAsString,
      credentials: rds.Credentials.fromGeneratedSecret('saihai_postgres'),
      backup: { retention: Duration.days(7) },
      removalPolicy: stage === 'prod' ? RemovalPolicy.RETAIN : RemovalPolicy.DESTROY,
      deletionProtection: stage === 'prod',
    });

    new CfnOutput(this, 'DbSecretArn', { value: cluster.secret?.secretArn ?? '' });
    new CfnOutput(this, 'DbWriterEndpoint', { value: cluster.clusterEndpoint.hostname });
    new CfnOutput(this, 'DbPort', { value: String(cluster.clusterEndpoint.port) });
    new CfnOutput(this, 'DbNameOut', { value: dbName.valueAsString });
  }
}
