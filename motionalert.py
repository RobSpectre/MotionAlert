import os
import glob
import argparse
import logging

from twilio.rest import TwilioRestClient
from twilio.exceptions import TwilioException

from boto.s3.connection import S3Connection
from boto.s3.key import Key


class MotionAlert(object):
    def __init__(self, account_sid=None, auth_token=None,
                 aws_access_key_id=None, aws_secret_key=None, s3_bucket=None,
                 twilio_number=None, receiving_number=None,
                 motion_target_dir=None, timestamp=None, body=None):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_key = aws_secret_key
        self.s3_bucket = s3_bucket
        self.twilio_number = twilio_number
        self.receiving_number = receiving_number
        self.motion_target_dir = motion_target_dir
        self.timestamp = timestamp
        self.body = body
        self.twilio_client = TwilioRestClient(self.account_sid,
                                              self.auth_token)

    def send(self):
        logging.info("Sending alert to {0}...".format(self.receiving_number))
        image_file_path = \
            self.get_latest_image_from_directory(self.motion_target_dir)
        if image_file_path:
            s3_upload = self.upload_image_to_s3(image_file_path,
                                                self.s3_bucket,
                                                self.timestamp)
        else:
            raise MotionAlertError("Could not retrieve an image to send.")

        if s3_upload:
            media_url = "https://s3.amazonaws.com/{0}" \
                        "/{1}".format(self.s3_bucket,
                                      self.timestamp)
            message = self.send_alert_to_phone_number(from_=self.twilio_number,
                                                      to=self.receiving_number,
                                                      body=self.body,
                                                      media_url=media_url)
            return message
        else:
            raise MotionAlertError("Could not send image to "
                                   "{0}.".format(self.receiving_number))

        if message:
            logging.info("Alert sent to {0}.".format(self.receiving_number))
        else:
            logging.error("An unknown error occured sending to "
                          "{0}.".format(self.receiving_number))

    def get_latest_image_from_directory(self, motion_target_dir):
        try:
            return max(glob.iglob('{0}/*.jpg'.format(motion_target_dir)),
                       key=os.path.getctime)
        except ValueError as e:
            raise MotionAlertError("Could not find any images in motion "
                                   "target directory: "
                                   "{0}".format(motion_target_dir))
        except OSError as e:
            raise MotionAlertError("Could not find the motion target dir: "
                                   "{0}".format(e))

    def upload_image_to_s3(self, image_file_path, bucket_name, key_name):
        try:
            s3_connection = S3Connection(self.aws_access_key_id,
                                         self.aws_secret_key)
        except Exception as e:
            raise MotionAlertError("Error connecting to S3: {0}".format(e))

        try:
            bucket = s3_connection.get_bucket(bucket_name)
        except Exception as e:
            raise MotionAlertError("Error connecting to S3 bucket: "
                                   "{0}".format(e))

        try:
            key = Key(bucket)
            key.key = key_name
            return key.set_contents_from_filename(image_file_path)
        except Exception as e:
            raise MotionAlertError("Error uploading file to S3: {0}".format(e))

    def send_alert_to_phone_number(self, from_=None, to=None, body=None,
                                   media_url=None):
        try:
            self.twilio_client.messages.create(from_=from_, to=to,
                                               body=body, media_url=media_url)
        except TwilioException as e:
            raise MotionAlertError("Error sending MMS with Twilio: "
                                   "{0}".format(e))


class MotionAlertError(Exception):
    def __init__(self, message):
        logging.error("ERROR: {0}".format(message))
        logging.error("Try running with --help for more information.")


parser = argparse.ArgumentParser(description="Motion Alert - send MMS alerts "
                                             "from Motion events.",
                                 epilog="Powered by Twilio!")

parser.add_argument("-S", "--account_sid", default=None, required=True,
                    help="Use a specific Twilio Account Sid.")
parser.add_argument("-K", "--auth_token", default=None, required=True,
                    help="Use a specific Twilio Auth Token.")
parser.add_argument("-#", "--twilio_number", default=None, required=True,
                    help="Use a specific Twilio phone number "
                         "(e.g. +15556667777).")
parser.add_argument("-s", "--aws_access_key_id", default=None, required=True,
                    help="Use a specific Amazon Web Services Access Key Id.")
parser.add_argument("-k", "--aws_secret_key", default=None, required=True,
                    help="Use a specific Amazon Web Services Secret Key.")
parser.add_argument("-b", "--s3_bucket", default=None, required=True,
                    help="Use a specific Amazon Web Services S3 Bucket.")
parser.add_argument("-t", "--receiving_number", default=None, required=True,
                    help="Number to receive the alerts.")
parser.add_argument("-T", "--timestamp", default=None, required=True,
                    help="Timestamp of event passed from Motion.")
parser.add_argument("-B", "--body", default=None, required=True,
                    help="Body of message you wish to send.")
parser.add_argument("-d", "--motion_target_dir", default=None, required=True,
                    help="Directory where Motion is storing images from "
                         "motion capture.")

logging.basicConfig(level=logging.INFO, format="%(message)s")

if __name__ == "__main__":
    motion_alert = MotionAlert()
    parser.parse_args(namespace=motion_alert)
    motion_alert.send()
