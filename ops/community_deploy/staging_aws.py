"""Fixed-resource adapters for the staging lifecycle core; no AWS client at import.

Clients are supplied by trusted installation code with bounded connect/read
timeouts and zero SDK retries for mutating operations. The caller supplies
independent guard/readiness probes. This is not a live Lambda entry point.
"""
import json
import re

try:
    from .staging_lifecycle import Refused, StateUnavailable, require
except ImportError:  # Reviewed copies installed outside the app checkout.
    from staging_lifecycle import Refused, StateUnavailable, require


def bounded_client(client):
    config = client.meta.config
    require(type(config.retries) is dict and config.retries.get('total_max_attempts') == 1,
            'sdk_retries_must_be_disabled')
    require(type(config.connect_timeout) in {int, float} and 0 < config.connect_timeout <= 5 and
            type(config.read_timeout) in {int, float} and 0 < config.read_timeout <= 10,
            'sdk_timeouts_must_be_bounded')


class S3State:
    def __init__(self, client, bucket, key, max_bytes=1_048_576):
        bounded_client(client)
        require(isinstance(bucket, str) and re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket),
                'invalid_state_bucket')
        require(isinstance(key, str) and re.fullmatch(r'[A-Za-z0-9_/-]+\.json', key) and
                '..' not in key, 'invalid_state_key')
        require(type(max_bytes) is int and 1 <= max_bytes <= 1_048_576, 'invalid_state_size_limit')
        self.client, self.bucket, self.key, self.max_bytes = client, bucket, key, max_bytes

    def read(self):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.key)
            stream = response['Body']
            try:
                raw = stream.read(self.max_bytes + 1)
            finally:
                stream.close()
            require(len(raw) <= self.max_bytes, 'state_size_limit')
            return json.loads(raw), response['ETag']
        except Exception:
            raise StateUnavailable('state_read_unavailable') from None

    def compare_and_swap(self, token, state):
        require(isinstance(token, str) and 1 <= len(token) <= 200, 'state_token_required')
        raw = json.dumps(state, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        require(len(raw) <= self.max_bytes, 'state_size_limit')
        try:
            result = self.client.put_object(Bucket=self.bucket, Key=self.key, Body=raw,
                ContentType='application/json', ServerSideEncryption='AES256', IfMatch=token)
            return result['ETag']
        except Exception:
            # No blind retry, including a 412 conflict or an uncertain HTTP result.
            raise StateUnavailable('conditional_state_write_unconfirmed') from None


class FixedCloud:
    def __init__(self, ec2, ssm, instance_id, document_version, verify_guards, ready_probe):
        bounded_client(ec2)
        bounded_client(ssm)
        try:
            from .staging_lifecycle import INSTANCE
        except ImportError:
            from staging_lifecycle import INSTANCE
        require(isinstance(instance_id, str) and INSTANCE.fullmatch(instance_id), 'invalid_instance')
        require(isinstance(document_version, str) and
                re.fullmatch(r'[1-9][0-9]{0,5}', document_version), 'fixed_document_version_required')
        require(callable(verify_guards) and callable(ready_probe), 'trusted_probes_required')
        self.ec2, self.ssm, self.instance = ec2, ssm, instance_id
        self.version, self.guard_probe, self.ready_probe = document_version, verify_guards, ready_probe

    def verify_guards(self, revision):
        require(self.guard_probe(revision) is True, 'shutdown_guards_not_verified')
        reply = self.ec2.describe_instance_attribute(InstanceId=self.instance,
                                                     Attribute='instanceInitiatedShutdownBehavior')
        require(reply.get('InstanceInitiatedShutdownBehavior', {}).get('Value') == 'stop',
                'host_shutdown_must_stop')

    def instance_state(self):
        result = self.ec2.describe_instances(InstanceIds=[self.instance])
        rows = [item for group in result.get('Reservations', []) for item in group.get('Instances', [])]
        require(len(rows) == 1 and rows[0].get('InstanceId') == self.instance,
                'instance_identity_not_confirmed')
        state = rows[0].get('State', {}).get('Name')
        require(state in {'pending', 'running', 'stopping', 'stopped'}, 'unsupported_instance_state')
        return state

    def start(self):
        self.ec2.start_instances(InstanceIds=[self.instance])

    def stop(self):
        self.ec2.stop_instances(InstanceIds=[self.instance])

    def ready(self, expected_sha, lease_id):
        return self.ready_probe(expected_sha, lease_id) is True

    def deploy(self, candidate, expected, lease_id):
        # All values are validated by Coordinator; the target and document are fixed.
        reply = self.ssm.send_command(InstanceIds=[self.instance],
            DocumentName='CLARA-DeployStaging', DocumentVersion=self.version,
            Parameters={'Commit': [candidate], 'ExpectedCommit': [expected], 'LeaseId': [lease_id]},
            TimeoutSeconds=600, Comment='Bounded staging lease ' + lease_id)
        return reply['Command']['CommandId']

    def receipt(self, command_id):
        try:
            reply = self.ssm.get_command_invocation(CommandId=command_id, InstanceId=self.instance)
        except Exception as error:
            # The only eventual-consistency error that means "not yet visible".
            if getattr(error, 'response', {}).get('Error', {}).get('Code') == 'InvocationDoesNotExist':
                return None
            raise Refused('command_read_unavailable') from None
        if reply.get('Status') in {'Pending', 'InProgress', 'Delayed'}:
            return None
        try:
            raw = reply['StandardOutputContent']
            require(isinstance(raw, str) and len(raw.encode()) <= 65_536, 'receipt_size_limit')
            receipt = json.loads(raw)
        except (KeyError, ValueError, TypeError, Refused):
            return {}  # Core treats an unverified terminal result as recovery-required.
        if type(receipt) is not dict:
            return {}
        # A nonzero SSM command may carry a valid recovered/refused host receipt.
        if reply.get('Status') != 'Success' and receipt.get('status') == 'installed':
            return {}
        return receipt
