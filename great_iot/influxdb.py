from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from django.conf import settings
import re
import datetime


class InfluxDBConnection:
    def __init__(self):
        self.settings = settings.INFLUXDB_SETTINGS
        self.client = InfluxDBClient(
            url=self.settings['url'],
            token=self.settings['token'],
            org=self.settings['org'],
            timeout=30000
        )
        self.query_api = self.client.query_api()
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.delete_api = self.client.delete_api()

    def write_point(self, measurement, tags, fields, timestamp=None):
        from influxdb_client import Point
        from datetime import timezone

        point = Point(measurement)
        for tag_name, tag_value in tags.items():
            point.tag(tag_name, tag_value)
        for field_name, field_value in fields.items():
            point.field(field_name, field_value)
        if timestamp is not None:
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.datetime.fromtimestamp(timestamp, tz=timezone.utc)
            point.time(timestamp)
        self.write_api.write(
            bucket=self.settings['bucket'], org=self.settings['org'], record=point
        )

    def get_time_series_data(
        self, measurement, field, start_time="-1h", stop_time=None, max_points=5000, tags=None
    ):
        range_str = f"start: {start_time}"
        if stop_time:
            range_str += f", stop: {stop_time}"

        tag_filter = ""
        if tags:
            for k, v in tags.items():
                tag_filter += f' |> filter(fn: (r) => r["{k}"] == "{v}")'

        sample_query = f'''
        from(bucket: "{self.settings['bucket']}")
        |> range({range_str})
        |> filter(fn: (r) => r._measurement == "{measurement}")
        |> filter(fn: (r) => r._field == "{field}")
        {tag_filter}
        |> count()
        '''

        try:
            sample_tables = self.query_api.query(sample_query, org=self.settings['org'])
            total_points = 0
            for table in sample_tables:
                for record in table.records:
                    if record.get_value():
                        total_points = record.get_value()
                        break

            if total_points > max_points:
                window_duration = self._calculate_window_duration(
                    start_time, stop_time, max_points, total_points
                )
                return self._get_aggregated_data(
                    measurement, field, start_time, stop_time, window_duration, max_points, tags
                )
            else:
                return self._get_raw_data(measurement, field, start_time, stop_time, tags)
        except Exception:
            return []

    def _calculate_window_duration(self, start_time, stop_time, max_points, total_points):
        try:
            from dateutil.parser import parse

            now = datetime.datetime.now(datetime.timezone.utc)
            stop_dt = parse(stop_time) if stop_time and "T" in stop_time else now
            if "T" in str(start_time):
                start_dt = parse(start_time)
                total_seconds = (stop_dt - start_dt).total_seconds()
            else:
                time_multipliers = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
                match = re.match(r"-?(\d+)([mhdw])", str(start_time))
                if not match:
                    total_seconds = 3600
                else:
                    duration_num = int(match.group(1))
                    duration_unit = match.group(2)
                    total_seconds = duration_num * time_multipliers.get(duration_unit, 3600)
        except Exception:
            total_seconds = 3600

        target_window_seconds = total_seconds / max_points
        if target_window_seconds < 60:
            return f"{max(1, int(target_window_seconds))}s"
        elif target_window_seconds < 3600:
            return f"{max(1, int(target_window_seconds / 60))}m"
        elif target_window_seconds < 86400:
            return f"{max(1, int(target_window_seconds / 3600))}h"
        else:
            return f"{max(1, int(target_window_seconds / 86400))}d"

    def _get_aggregated_data(
        self, measurement, field, start_time, stop_time, window_duration, max_points, tags=None
    ):
        range_str = f"start: {start_time}"
        if stop_time:
            range_str += f", stop: {stop_time}"

        tag_filter = ""
        if tags:
            for k, v in tags.items():
                tag_filter += f' |> filter(fn: (r) => r["{k}"] == "{v}")'

        query = f'''
        from(bucket: "{self.settings['bucket']}")
        |> range({range_str})
        |> filter(fn: (r) => r._measurement == "{measurement}")
        |> filter(fn: (r) => r._field == "{field}")
        {tag_filter}
        |> aggregateWindow(every: {window_duration}, fn: mean, createEmpty: false)
        |> sort(columns: ["_time"])
        '''

        try:
            tables = self.query_api.query(query, org=self.settings['org'])
            data = []
            for table in tables:
                for record in table.records:
                    data.append(
                        {
                            "time": record.get_time().isoformat(),
                            "value": (
                                round(record.get_value(), 4)
                                if record.get_value() is not None
                                else 0
                            ),
                            "field": record.get_field(),
                            "measurement": record.get_measurement(),
                            "is_aggregated": True,
                            "window_duration": window_duration,
                        }
                    )
            return data
        except Exception:
            return self._get_raw_data(measurement, field, start_time)

    def _get_raw_data(self, measurement, field, start_time, stop_time, tags=None):
        range_str = f"start: {start_time}"
        if stop_time:
            range_str += f", stop: {stop_time}"

        tag_filter = ""
        if tags:
            for k, v in tags.items():
                tag_filter += f' |> filter(fn: (r) => r["{k}"] == "{v}")'

        query = f'''
        from(bucket: "{self.settings['bucket']}")
        |> range({range_str})
        |> filter(fn: (r) => r._measurement == "{measurement}")
        |> filter(fn: (r) => r._field == "{field}")
        {tag_filter}
        |> sort(columns: ["_time"])
        '''

        try:
            tables = self.query_api.query(query, org=self.settings['org'])
            data = []
            for table in tables:
                for record in table.records:
                    data.append(
                        {
                            "time": record.get_time().isoformat(),
                            "value": record.get_value(),
                            "field": record.get_field(),
                            "measurement": record.get_measurement(),
                            "is_aggregated": False,
                        }
                    )
            return data
        except Exception:
            return []

    def get_measurements(self):
        query = f'import "influxdata/influxdb/schema"\nschema.measurements(bucket: "{self.settings["bucket"]}")'
        tables = self.query_api.query(query, org=self.settings["org"])
        measurements = []
        for table in tables:
            for record in table.records:
                measurements.append(record.get_value())
        return sorted(measurements)

    def get_fields(self, measurement):
        query = f'''
from(bucket: "{self.settings["bucket"]}")
  |> range(start: -1y)
  |> filter(fn: (r) => r._measurement == "{measurement}")
  |> distinct(column: "_field")
'''
        tables = self.query_api.query(query, org=self.settings["org"])
        fields = set()
        for table in tables:
            for record in table.records:
                if record.get_value():
                    fields.add(record.get_value())
        return sorted(fields)

    def get_latest_data(self, measurement, tags=None):
        tag_filter = ""
        if tags:
            for k, v in tags.items():
                tag_filter += f' |> filter(fn: (r) => r["{k}"] == "{v}")'

        query = f'from(bucket: "{self.settings["bucket"]}") |> range(start: -24h) |> filter(fn: (r) => r._measurement == "{measurement}") {tag_filter} |> last()'
        try:
            tables = self.query_api.query(query, org=self.settings["org"])
            latest_data = {}
            for table in tables:
                for record in table.records:
                    latest_data[record.get_field()] = record.get_value()
            return latest_data
        except Exception:
            return {}

    def delete_data(self, measurement, tags=None):
        start = "1970-01-01T00:00:00Z"
        stop = datetime.datetime.now(datetime.timezone.utc).isoformat()

        predicate = f'_measurement="{measurement}"'
        if tags:
            for k, v in tags.items():
                predicate += f' AND "{k}"="{v}"'

        try:
            self.delete_api.delete(
                start, stop, predicate, bucket=self.settings["bucket"], org=self.settings["org"]
            )
            return True
        except Exception:
            return False

    def close(self):
        self.client.close()
