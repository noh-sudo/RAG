# 회의록 요약 RAG 프로젝트

push 할땐 반드시 새 브랜치 + 디렉토리로 해주세요!!
```
ex) git clone <github주소> / git pull origin
    새 디렉토리 생성(easymode) + 작업
    git checkout -b feature/easymode
    git add .
    git commit -m "easymode 추가"
    git push -u origin feature/easymode
```

+ 7/31 feature/data 추가
+ 8/1  feature/rag 추가
+ 8/2  feature/gui 추가
+ 8/3  main 병합
----
<br>
<br>
<br>
<br>
<br>

----

## ollama 다운로드
본 프로젝트는 ollama 로컬 임베딩 모델 bge-m3와 llm 모델 gemma4:12b를 필요로 합니다.
먼저 로컬 ollama를 다운로드 받아주세요.

```
sudo apt update
sudo apt install ollama
```

ollama 다운로드가 완료되면 모델을 다운로드 받아주세요.

```
ollama pull bge-m3
ollama pull gemma4:12b
``` 

두 모델이 확인되면 성공입니다.

```
ollama list
```
ex) bge-m3, gemma4:12b

----
## 서버를 키기전 확인해주세요
본 프로젝트는 TCP/IP 소켓 프로토콜을 기반으로 서버/클라이언트를 구현했습니다.
원천 라벨링 데이터를 확보해주세요. [링크](https://aihub.or.kr/aihubdata/data/view.do?pageIndex=1&currMenu=&topMenu=&srchOptnCnd=OPTNCND001&searchKeyword=%EA%B5%AD%ED%9A%8C&srchDetailCnd=DETAILCND001&srchOrder=ORDER001&srchPagePer=20&srchDataRealmCode=REALM002&aihubDataSe=data&dataSetSn=71795)

server.py를 실행하기 전 chunk_builder.py와 build_dense.py를 순서대로 실행해 데이터를 준비해주세요.

data/chunks.json과 data/chroma/ 가 생성되었고 config.py의 설정과 일치한다면 서버를 실행할 수 있습니다.

1. server.py 실행 (동일한 구성을 위해 가급적 다른 pc에서 실행하는걸 추천합니다.)
2. 현재 pc에서 main.py 실행
3. gui사용
