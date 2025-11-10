pipeline {
    agent any

    environment {
        REPORTS_DIR = "reports"
        PYTHON_PATH = "/usr/bin/python3"
        VENV_PATH = ".venv"
    }

    stages {
        stage('Setup Python Environment') {
            steps {
                // Create a per-job virtualenv to avoid system-managed pip issues (PEP 668)
                sh '''
                    set -e
                    echo "Creating virtualenv at ${VENV_PATH}"
                    ${PYTHON_PATH} -m venv ${VENV_PATH}
                    ${VENV_PATH}/bin/python -m pip install --upgrade pip
                    ${VENV_PATH}/bin/pip install --upgrade requests selenium locust pytest pytest-html junit-xml
                    ${VENV_PATH}/bin/python -m pip show pytest || true
                '''
            }
        }

        stage('Checkout') {
            steps {
                // Use the same SCM that started the pipeline (reuses credentials configured in the job)
                // This avoids switching to an unauthenticated HTTPS fetch which can fail for private repos.
                checkout scm
                sh 'mkdir -p ${REPORTS_DIR}'
                sh 'ls -la'
            }
        }

        stage('Start OpenBMC in QEMU') {
            steps {
                echo "Starting OpenBMC QEMU instance..."
                sh '''
                    set -e
                    chmod +x OBMC-Romulus-image.mtd 2>/dev/null || true

                    # Kill leftover qemu if any
                    pkill -f qemu-system-arm || true
                    sleep 1 || true

                    # Запускаем QEMU в фоне и направляем консоль в файл
                    nohup qemu-system-arm -m 256 -M romulus-bmc -nographic -drive file=./OBMC-Romulus-image.mtd,format=raw,if=mtd -net nic -net user,hostfwd=:0.0.0.0:2222-:22,hostfwd=:0.0.0.0:2443-:443,hostfwd=udp:0.0.0.0:2623-:623,hostname=qemu \
                        > ${REPORTS_DIR}/qemu_console.log 2>&1 &

                    # Ждем загрузки системы с повторными проверками (up to ~3 minutes)
                    echo "Waiting for OpenBMC to boot (checking HTTPS port)..."
                    for i in $(seq 1 18); do
                        if curl -k --connect-timeout 5 https://127.0.0.1:2443 -I >/dev/null 2>&1; then
                            echo "OpenBMC web service is up"
                            break
                        fi
                        echo "waiting... ($i)"
                        sleep 10
                    done

                    # Дамп последних строк консоли
                    tail -n 200 ${REPORTS_DIR}/qemu_console.log || true
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "${REPORTS_DIR}/qemu_console.log", fingerprint: true
                }
            }
        }

        stage('Wait for OpenBMC Services') {
            steps {
                sh '''
                    echo "Checking OpenBMC services (SSH/HTTPS)"
                    for i in $(seq 1 12); do
                        printf "Attempt %d: " "$i"
                        if curl -k --connect-timeout 5 https://127.0.0.1:2443 -I >/dev/null 2>&1; then
                            echo "HTTPS OK"
                            break
                        fi
                        sleep 5
                    done

                    if nc -zv 127.0.0.1 2222 >/dev/null 2>&1; then
                        echo "SSH forwarded port reachable"
                    else
                        echo "SSH forwarded port not reachable (2222)"
                    fi
                '''
            }
        }

        stage('Run Redfish API Tests') {
            steps {
                echo "Running Redfish API Tests..."
                sh '''
                    set -o pipefail
                    ${VENV_PATH}/bin/python -m pytest tests_Redfish.py --junitxml=${REPORTS_DIR}/redfish_results.xml -v 2>&1 | tee ${REPORTS_DIR}/redfish_pytest.log || true
                '''
            }
            post {
                always {
                    junit "${REPORTS_DIR}/redfish_results.xml"
                    archiveArtifacts artifacts: "${REPORTS_DIR}/redfish_pytest.log, ${REPORTS_DIR}/redfish_results.xml", fingerprint: true
                }
            }
        }

        stage('Run WebUI Tests') {
            steps {
                echo "Running WebUI Selenium Tests..."
                sh '''
                    set -o pipefail
                    ${VENV_PATH}/bin/python -m pytest tests_WebUI.py --html=${REPORTS_DIR}/webui_report.html --self-contained-html -v 2>&1 | tee ${REPORTS_DIR}/webui_pytest.log || true
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "${REPORTS_DIR}/webui_report.html, ${REPORTS_DIR}/webui_pytest.log", fingerprint: true
                    publishHTML(target: [
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: "${REPORTS_DIR}",
                        reportFiles: "webui_report.html",
                        reportName: "WebUI Test Report"
                    ])
                }
            }
        }

        stage('Run Load Tests') {
            steps {
                echo "Running Locust Load Tests..."
                sh '''
                    set -o pipefail
                    # Запуск теста локально (скрипт должен формировать отчеты в reports/)
                    ${VENV_PATH}/bin/python tests_Locust.py > ${REPORTS_DIR}/locust_log.txt 2>&1 || true
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "${REPORTS_DIR}/locust_log.txt, ${REPORTS_DIR}/locust_report.html", fingerprint: true
                }
            }
        }
    }

    post {
        always {
            echo "Cleaning up QEMU processes..."
            sh '''
                pkill -f qemu-system-arm || true
                sleep 5
                # Принудительное завершение если нужно
                pkill -9 -f qemu-system-arm || true
            '''
        }
    }
}
