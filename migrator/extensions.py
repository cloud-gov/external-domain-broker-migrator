import boto3

from migrator.config import config_from_env


config = config_from_env()


commercial_session = boto3.Session(
    region_name=config.AWS_COMMERCIAL_REGION,
    aws_access_key_id=config.AWS_COMMERCIAL_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_COMMERCIAL_SECRET_ACCESS_KEY,
)
cloudfront = commercial_session.client("cloudfront")
iam_commercial = commercial_session.client("iam")
