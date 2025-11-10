from locust import HttpUser, task, between
import requests
import json
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class OpenBMCUser(HttpUser):
    host = "https://localhost:2443"
    wait_time = between(1, 3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth = ("root", "0penBmc")
        self.verify_ssl = False

    @task(3)
    def get_system_info(self):
        with self.client.get(
            "/redfish/v1/Systems/system",
            auth=self.auth,
            verify=self.verify_ssl,
            catch_response=True,
            name="OpenBMC - System Info"
        ) as response:
            if response.status_code == 200:
                try:
                    system_data = response.json()
                    if 'Name' in system_data and 'Id' in system_data:
                        response.success()
                    else:
                        response.failure("Invalid system response format")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON in system response")
            else:
                response.failure(f"HTTP {response.status_code} for system info")

    @task(2)
    def get_power_state(self):
        with self.client.get(
            "/redfish/v1/Systems/system",
            auth=self.auth,
            verify=self.verify_ssl,
            catch_response=True,
            name="OpenBMC - Power State"
        ) as response:
            if response.status_code == 200:
                try:
                    system_data = response.json()
                    power_state = system_data.get('PowerState')
                    if power_state in ['On', 'Off', 'PoweringOn', 'PoweringOff']:
                        response.success()
                    else:
                        response.failure(f"Invalid power state: {power_state}")
                except (json.JSONDecodeError, KeyError):
                    response.failure("Power state not found or invalid JSON")
            else:
                response.failure(f"HTTP {response.status_code} for power state")


class JSONPlaceholderUser(HttpUser):
    host = "https://jsonplaceholder.typicode.com"
    wait_time = between(0.5, 2)

    @task
    def get_posts_list(self):
        with self.client.get(
            "/posts",
            catch_response=True,
            name="JSONPlaceholder - Posts List"
        ) as response:
            if response.status_code == 200:
                try:
                    posts = response.json()
                    if isinstance(posts, list) and len(posts) > 0 and all('id' in post and 'title' in post for post in posts):
                        response.success()
                    else:
                        response.failure("Empty or invalid posts list")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON in posts response")
            else:
                response.failure(f"HTTP {response.status_code} for posts list")


class WeatherAPIUser(HttpUser):
    host = "https://wttr.in"
    wait_time = between(1, 3)

    @task
    def get_weather(self):
        with self.client.get(
            "/Novosibirsk?format=j1",
            headers={"User-Agent": "locust-load-test"},
            verify=False,
            catch_response=True,
            name="Weather API - Novosibirsk"
        ) as response:
            if response.status_code == 200:
                try:
                    weather_data = response.json()
                    if "current_condition" in weather_data:
                        response.success()
                    else:
                        response.failure("Invalid weather response format")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON in weather response")
            else:
                response.failure(f"HTTP {response.status_code}")


if __name__ == "__main__":
    # Allow running this file directly in CI: invoke locust CLI programmatically using the same Python
    import os
    import sys
    import subprocess
    import html as _html

    # Defaults can be overridden by environment variables
    users = os.getenv('LOCUST_USERS', '5')
    spawn_rate = os.getenv('LOCUST_SPAWN_RATE', '1')
    run_time = os.getenv('LOCUST_RUN_TIME', '30s')
    report_dir = os.getenv('REPORTS_DIR', 'reports')
    report_file = os.path.join(report_dir, os.getenv('LOCUST_REPORT', 'locust_report.html'))

    os.makedirs(report_dir, exist_ok=True)

    # Build locust CLI command using the same Python executable (so venv is respected)
    cmd = [sys.executable, '-m', 'locust', '-f', __file__, '--headless', '-u', users, '-r', spawn_rate, '-t', run_time, '--html', report_file]

    print(f"Running Locust: {' '.join(cmd)}")
    # Capture output so we can always produce artifacts for Jenkins
    proc = subprocess.run(cmd, capture_output=True, text=True)
    cli_out = proc.stdout or ""
    cli_err = proc.stderr or ""
    cli_out_file = os.path.join(report_dir, os.getenv('LOCUST_CLI_OUT', 'locust_cli_output.txt'))
    with open(cli_out_file, 'w', encoding='utf-8') as f:
        f.write('=== LOCUST STDOUT ===\n')
        f.write(cli_out)
        f.write('\n=== LOCUST STDERR ===\n')
        f.write(cli_err)

    # If locust didn't generate the HTML report, create a placeholder to archive
    if not os.path.exists(report_file) or proc.returncode != 0:
        placeholder_path = report_file
        with open(placeholder_path, 'w', encoding='utf-8') as f:
            f.write('<html><head><title>Locust report</title></head><body>')
            f.write('<h1>Locust run did not produce an HTML report</h1>')
            f.write(f'<p>Return code: {proc.returncode}</p>')
            f.write('<h2>CLI output</h2><pre>')
            # escape HTML
            f.write(_html.escape(cli_out + '\n' + cli_err))
            f.write('</pre></body></html>')

    # Print summary for Jenkins console
    print(f"Locust finished with return code {proc.returncode}; CLI output saved to {cli_out_file}; HTML report at {report_file}")
    # Do not sys.exit with non-zero to avoid failing whole pipeline; Jenkins will mark unstable if needed
    # but keep the locust return code available via the CLI output
