from plugins.cleaning import Cleaning
from airflow import DAG
from datetime import timedelta
from airflow.decorators import task
from plugins import filter
from utils import FileManager
from s3 import S3Helper
from airflow.sensors.external_task import ExternalTaskSensor

import datetime
import logging

@task
def cleaning(**context):
    try:
        execution_date = context['execution_date'].date()
        data = Cleaning.read_csv_to_df('air', execution_date, filter.column_indexes['air'])
        data = Cleaning.rename_cols(data, 'air')
        data = Cleaning.check_pk_validation(data, 'gu')

        result_data = Cleaning.unify_null(data)
        result_data = Cleaning.filter(result_data, 'air')

        save_path = 'temp/seoul_air/cleaning/'
        file_name = f'{execution_date}.parquet'
        path = save_path+file_name

        FileManager.mkdir(save_path)

        result_data.to_parquet(path, index=False)

        s3_key = 'cleaned_data/seoul_air/' + file_name

        S3Helper.upload(aws_conn_id, bucket_name, s3_key, path, True)

        FileManager.remove(path)

    except Exception as e:
        logging.info(e)
        pass


with DAG(
    dag_id = 'air_cleaning_',
    start_date = datetime.datetime(2024,1,1),
    schedule = '@daily',
    max_active_runs = 1,
    catchup = True,
    default_args = {
        'retries': 1,
        'retry_delay': timedelta(minutes=1),
    }
) as dag:
    aws_conn_id='aws_default'
    bucket_name = 'de-team5-s3-01'

    sensor = ExternalTaskSensor(
        task_id='externaltasksensor',
        external_dag_id='etl_seoul_air__',
        external_task_id='load',
        timeout=5*60,
        mode='reschedule',
        allowed_states=['success'],
        dag=dag
)

    cleaning_task = cleaning()

    sensor >> cleaning_task
