# G-Cube Wheelchair & Weather Umbrella

4개의 G-큐브를 하나의 그룹 ID로 연결해 휠체어 주행, 우산 자동·수동 개폐, LED 매트릭스 날씨 표시를 수행하는 독립 Python 프로젝트입니다.

Python 버전은 Teachable Machine을 사용하지 않습니다. 날씨 입력은 기상청 초단기실황 API만 사용합니다.

## 하드웨어 구성

| 역할 | 통합 그룹 | Cube 번호 | 동작 |
|---|---:|---:|---|
| 왼쪽 구동축 | `GROUP_ID` | Cube 1 | 연속 스테퍼 구동 |
| 오른쪽 구동축 | `GROUP_ID` | Cube 2 | 연속 스테퍼 구동 |
| 우산 제어 | `GROUP_ID` | Cube 3 | 상대 90도, 기본 500스텝 |
| LED 매트릭스 | `GROUP_ID` | Cube 4 | 8×8 날씨 아이콘 표시 |

4개 로봇은 모두 `.env`의 `GROUP_ID` 하나를 사용합니다. 기본값은 `02`입니다.

## 주요 기능

- 방향키를 누르는 동안 전진, 후진, 좌회전, 우회전
- 화면에서 Robot 1~4의 왼쪽 바퀴·오른쪽 바퀴·우산·LED 역할 선택
- 방향키를 놓으면 휠 자동 정지
- `Space` 또는 비상 정지 버튼으로 구동축과 우산 모터 정지
- 화면 버튼을 이용한 우산 수동 펼치기·접기
- 기상청 `PTY` 및 `RN1` 기반 우산 자동 개폐
- 맑은 날 Cube 4에 해 아이콘 표시
- 강수 시 Cube 4에 우산 아이콘 표시
- 우산을 접으면 해, 펼치면 비 아이콘을 항상 3초간 표시한 뒤 자동으로 지움
- 우산 동작에만 TTS 사용

TTS 문장은 다음 두 개로 제한됩니다.

```text
우산을 펼칩니다
우산을 접습니다
```

연결 완료, 주행, 날씨 조회 및 사용자 문구에는 TTS를 사용하지 않습니다.

## Scratch 수정본 분석

다음 파일을 `reference/`에 보존했습니다.

```text
날씨를 감지해서 펼치고 접는 휠체어 우산 - 수정본.sb3
```

Scratch 수정본은 Teachable Machine 분류에 따라 우산을 제어하고 LED 매트릭스에 날씨 그림을 표시합니다. Python 프로그램에서는 Scratch의 Teachable Machine 모델과 카메라 코드를 사용하지 않고, 날씨 입력 부분을 기상청 API로 완전히 대체했습니다.

수정본의 기존 해 그림은 중심과 광선이 비대칭이었습니다. `reference/`에 복사한 Scratch 수정본의 해 블록 2개와 Python 버전 모두 다음과 같이 좌우·상하 대칭인 해 패턴으로 교체했습니다.

```text
..#..#..
...##...
.#.##.#.
#.####.#
#.####.#
.#.##.#.
...##...
..#..#..
```

## 설치

실행 전에 기존 PingPong 웹 대시보드와 Scratch Desktop의 BLE 연결을 종료하십시오. 하나의 BLE 장치를 여러 프로그램이 동시에 사용할 수 없습니다.

```powershell
cd path\to\wheelchair_umbrella
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
```

## 환경 설정

`.env`에서 API 키, 통합 그룹 ID와 모터 방향을 설정합니다. `.env`는 Git에서 제외됩니다.

```dotenv
KMA_SERVICE_KEY=발급받은_인증키
KMA_NX=60
KMA_NY=127

GROUP_ID=02
LEFT_WHEEL_CUBE=1
RIGHT_WHEEL_CUBE=2
UMBRELLA_CUBE=3
LED_MATRIX_CUBE=4
BLE_ADDRESS=
LED_BRIGHTNESS=8

LEFT_MOTOR_SIGN=1
RIGHT_MOTOR_SIGN=-1
UMBRELLA_OPEN_SIGN=1
```

`BLE_ADDRESS`를 비워 두면 `GROUP_ID`와 일치하는 광고 장치를 자동 검색합니다.
역할별 Cube 번호는 `1`부터 `4`까지 서로 겹치지 않게 지정해야 합니다.

프로그램 상단의 `로봇 역할 선택` 메뉴에서도 역할을 변경할 수 있습니다. 연결 중 역할을 적용하면 기존 매핑으로 모터를 먼저 정지한 후 새 매핑으로 전환합니다. 선택 결과는 Git에서 제외되는 `robot_roles.json`에 저장되어 다음 실행에도 유지됩니다.

우산 버튼을 눌렀을 때 바퀴가 움직이면 물리적인 체인 순서와 역할 설정이 다른 상태입니다. `우산` 드롭다운을 실제 우산 모터 Robot으로 변경하고 나머지 역할도 중복되지 않게 배치한 후 `선택 적용`을 누르십시오.

4-Cube 그룹의 우산 모터 명령은 단일 패킷으로 보내지 않고 aggregate 패킷 안에 선택한 Robot 번호를 넣어 전송합니다. 따라서 마스터 Robot이 우산 명령을 대신 실행하는 문제를 방지합니다.

## 기상청 API

1. [공공데이터포털 기상청 단기예보 조회서비스](https://www.data.go.kr/data/15084084/openapi.do)에서 활용 신청 후 인증키를 발급받습니다.
2. `.env`의 `KMA_SERVICE_KEY`에 일반 인증키를 입력합니다.
3. 설치 지역에 맞는 단기예보 격자 `KMA_NX`, `KMA_NY`를 입력합니다.

기본 `60,127`은 서울 중심부 예시입니다. 단기예보는 5 km 격자 좌표를 사용하므로 위도·경도를 직접 입력하면 안 됩니다.

사용 엔드포인트:

```text
https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst
```

관측 자료 게시 지연을 고려해 현재 시각에서 45분 이전의 정시를 먼저 조회하며, 데이터가 없으면 이전 2개 시각까지 재시도합니다.

강수 판단 기본 코드:

- `0`: 강수 없음
- `1`: 비
- `2`: 비/눈
- `3`: 눈
- `5`: 빗방울
- `6`: 빗방울/눈날림
- `7`: 눈날림

`PTY`가 `1,2,3,5,6,7` 중 하나이거나 `RN1 > 0`이면 강수 상태로 판단합니다. `RAIN_PTY_CODES`를 변경해 현장 정책에 맞출 수 있습니다.

공식 참고 자료:

- [공공데이터포털 단기예보 API](https://www.data.go.kr/data/15084084/openapi.do)
- [공공데이터포털 기상청 데이터 목록](https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EA%B8%B0%EC%83%81%EC%B2%AD)
- [기상청 단기예보 서비스 API 변경사항](https://apihub.kma.go.kr/getAttachFile.do?fileName=%2820241128%29%EB%8B%A8%EA%B8%B0%EC%98%88%EB%B3%B4+%EC%84%9C%EB%B9%84%EC%8A%A4+%EA%B0%9C%EC%84%A0%EC%97%90+%EB%94%B0%EB%A5%B8+API+%EB%B3%80%EA%B2%BD%EC%82%AC%ED%95%AD.pdf)

## 실행

```powershell
python .\main.py
```

1. `BLE 연결` 버튼을 누릅니다.
2. 동일 그룹의 G-큐브 4개 연결을 확인합니다.
3. 방향키 또는 화면 방향 버튼으로 주행합니다.
4. 우산을 수동 제어하거나 날씨 자동 제어를 사용합니다.
5. Cube 4의 해 또는 우산 아이콘을 확인합니다.

## 방향 및 밝기 보정

전진 시 한쪽 휠이 반대로 회전하면 해당 모터 부호를 바꿉니다.

```dotenv
LEFT_MOTOR_SIGN=1
RIGHT_MOTOR_SIGN=-1
```

우산 펼침과 접힘이 반대라면 다음 값을 변경합니다.

```dotenv
UMBRELLA_OPEN_SIGN=-1
```

LED 밝기는 `0`부터 `15`까지 설정할 수 있습니다.

```dotenv
LED_BRIGHTNESS=8
```

## 테스트

```powershell
python -m unittest discover -s .\tests -v
```

테스트는 실제 모터를 움직이지 않고 다음 항목을 검사합니다.

- 4-Cube 단일 그룹 연결 패킷
- Cube 1·2 구동축 aggregate 패킷
- Cube 3 우산 90도 패킷
- Cube 4 LED 매트릭스 패킷
- 해 패턴 좌우·상하 대칭
- 기상청 응답과 강수 판정

## 안전 주의

이 프로젝트는 시제품 제어 소프트웨어입니다. 사람이 탑승한 실제 휠체어에 적용하기 전에 물리 비상 정지, 전원 차단, 속도·토크 제한, 장애물 감지, 통신 끊김 자동 정지 및 우산 리미트 스위치를 별도로 확보해야 합니다.

날씨 API 또는 네트워크 장애 시 자동 우산과 LED 날씨 갱신은 수행되지 않지만 수동 우산 버튼과 주행 제어는 계속 사용할 수 있습니다.
