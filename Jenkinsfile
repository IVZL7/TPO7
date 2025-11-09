pipeline {
    agent any

    environment {
        REPORTS_DIR = "reports"
    }

    stages {
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
                nohup qemu-system-arm -m 256 -M romulus-bmc -nographic \
                    -drive file=OBMC-Romulus-image.mtd,format=raw,if=mtd \
                    -net nic -net user,hostfwd=:0.0.0.0:2222-:22,hostfwd=:0.0.0.0:2443-:443,hostfwd=udp:0.0.0.0:2623-:623,hostname=qemu \
                    > ${REPORTS_DIR}/qemu_console.log 2>&1 &
                sleep 20
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "${REPORTS_DIR}/qemu_console.log", fingerprint: true
                }
            }
        }

        stage('Run Redfish API Tests') {
            steps {
                echo "Running Redfish API Tests..."
                sh '''
                pytest tests_Redfish.py --junitxml=${REPORTS_DIR}/redfish_results.xml || true
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
                pytest tests_WebUI.py --html=${REPORTS_DIR}/webui_report.html --self-contained-html || true
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
            echo "Stopping QEMU if still running..."
            sh 'pkill qemu-system-arm || true'
        }
    }
}
