pipeline {
    agent any

    environment {
        REPORTS_DIR = "reports"
        PYTHON_PATH = "/usr/bin/python3"
    }

    stages {
        stage('Setup Python Environment') {
            steps {
                sh '''
                    python3 -m pip install --upgrade pip
                    pip3 install requests selenium locust pytest pytest-html
                '''
            }
        }

        stage('Checkout') {
            steps {
                git 'https://github.com/IVZL7/TPO7.git'
                sh 'mkdir -p ${REPORTS_DIR}'
            }
        }

        stage('Start OpenBMC in QEMU') {
            steps {
                echo "Starting OpenBMC QEMU instance..."
                sh '''
                    # Даем права на выполнение если нужно
                    chmod +x OBMC-Romulus-image.mtd 2>/dev/null || true
                    
                    # Запускаем QEMU в фоне
                    nohup qemu-system-arm -m 256 -M romulus-bmc -nographic \
                        -drive file=OBMC-Romulus-image.mtd,format=raw,if=mtd \
                        -net nic -net user,hostfwd=:0.0.0.0:2222-:22,hostfwd=:0.0.0.0:2443-:443,hostfwd=udp:0.0.0.0:2623-:623,hostname=qemu \
                        > ${REPORTS_DIR}/qemu_console.log 2>&1 &
                    
                    # Ждем загрузки системы
                    echo "Waiting for OpenBMC to boot..."
                    sleep 60
                    
                    # Проверяем, запустился ли процесс QEMU
                    ps aux | grep qemu
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
                    # Ждем доступности сервисов
                    echo "Waiting for OpenBMC services to start..."
                    sleep 30
                    
                    # Проверяем доступность веб-интерфейса
                    curl -k -I https://localhost:2443 || echo "Web interface not ready yet"
                '''
            }
        }

        stage('Run Redfish API Tests') {
            steps {
                echo "Running Redfish API Tests..."
                sh '''
                    python3 -m pytest tests_Redfish.py --junitxml=${REPORTS_DIR}/redfish_results.xml -v || true
                '''
            }
            post {
                always {
                    junit "${REPORTS_DIR}/redfish_results.xml"
                }
            }
        }

        stage('Run WebUI Tests') {
            steps {
                echo "Running WebUI Selenium Tests..."
                sh '''
                    python3 -m pytest tests_WebUI.py --html=${REPORTS_DIR}/webui_report.html --self-contained-html -v || true
                '''
            }
            post {
                always {
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
                    python3 tests_Locust.py > ${REPORTS_DIR}/locust_log.txt 2>&1 || true
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "${REPORTS_DIR}/locust_log.txt", fingerprint: true
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
