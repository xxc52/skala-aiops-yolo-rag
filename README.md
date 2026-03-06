## FarmLens
AI를 활용한 농작물 병충해 진단 및 솔루션 제공 서비스

### Enviroments
- `python == 3.11`
- `fastapi == 0.135.1`
- `torch==2.10.0`
- `torchvision==0.25.0`   
   
### 실행
- .env 파일 생성
```
OPENAI_API_KEY= {your OpenAIP Key}
DB_CONFIG={your PostgresDB URL}
```
- 환경 설정 <br>
`pip install -r requirements.txt`
- BE 실행 <br>
`python -m uvicorn app.main:app --reload --port 8008`


### 프론트엔드 실행
```
cd SKALA_DEMO_LIM/vue-app
npm install
npm run dev
```
