# Mobilgene Config Studio

범용 Mobilgene / AUTOSAR R4.x 워크스페이스 **ARXML 뷰어** (P0: 읽기 전용 UI).

## 빠른 시작

**Cursor / PowerShell 터미널에서:**

```powershell
cd c:\MyJob\3.Mobilgene_Config_Studio
.\run-dev.ps1
```

**탐색기에서 더블클릭할 때:** `run-dev.bat` 사용  
(`.ps1`만 더블클릭하면 Windows가 “앱을 선택하여 열기” 창을 띄울 수 있습니다.)

서버 기동 후 브라우저가 자동으로 http://127.0.0.1:8765 를 엽니다.

테스트 워크스페이스: `2.AD_Gateway/AD_Gateway/rgw_working`

## 레이아웃

| 패널 | 역할 |
|------|------|
| 파일 트리 | 워크스페이스 ARXML 목록, 프로필·편집 가능 배지 |
| 설정 뷰 | 프로필별 뷰 (Gateway 매트릭스, ECUC 컨테이너, XML 트리) |
| 속성 | 선택 항목 상세 (P1+ 편집 폼 확장 예정) |

## 프로필

- `gateway` — I-PDU 매핑 테이블
- `ecuc` — ECUC 컨테이너·파라미터 요약
- `generic` — XML 트리 (폴백)

스키마: `schemas/profiles/*.json`

## 구조

```
├── ui/                 WebView (정적 HTML/JS/CSS)
├── scripts/            dev_server.py, arxml_parser.py
├── schemas/profiles/   UI 프로필 정의
├── src-tauri/          Tauri 2 (배포용, 진행 중)
├── cursor_direction.md 지침서
└── run-dev.ps1
```

## API (개발 서버)

| Endpoint | 설명 |
|----------|------|
| `POST /api/open_workspace` | 워크스페이스 열기 |
| `GET /api/workspace` | ARXML 목록 |
| `GET /api/index?file=` | 얕은 XML 인덱스 |
| `GET /api/gateway?file=` | Gateway 매핑 |
| `GET /api/ecuc?file=` | ECUC 컨테이너 요약 |
| `GET /api/properties?file=&path=` | 노드 속성 |

## 로드맵

- **P0** (현재): 파일 트리 + ARXML 읽기 전용 뷰
- **P1**: Gateway 매핑 CRUD + 저장
- **P2+**: Ecuc 편집, REF 점프, Tauri 단일 exe
