#!/usr/bin/env python3
"""
Notion → publications.json 동기화 스크립트
BLISS Lab 웹사이트용: Notion DB에서 논문/특허 데이터를 가져와 JSON으로 변환

사용법:
  Cowork에서 "논문 데이터 동기화해줘" 또는 "Notion에서 publications 업데이트해줘" 라고 요청
  → 이 스크립트의 로직을 Cowork가 실행하여 data/publications.json을 업데이트

Notion DB ID: 4b7523f8178b4502933eba18bbf7891d
"""

# 이 스크립트는 직접 실행하지 않고, Cowork 세션에서 Notion MCP를 통해 실행됩니다.
# 동기화 흐름:
#
# 1. Notion DB에서 모든 Publications 조회 (Type=Paper)
# 2. Number 기준 내림차순 정렬
# 3. data/publications.json 형식으로 변환:
#    {
#      "publications": [
#        {
#          "number": 91,
#          "year": 2026,
#          "title": "...",
#          "authors": "...",
#          "journal": "...",
#          "impactFactor": 20.3,
#          "image": "images/publications/pub-91.png"
#        }, ...
#      ],
#      "patents": [
#        {
#          "title": "...",
#          "titleEn": "...",
#          "inventors": "...",
#          "number": "10-2024-XXXXXXX",
#          "status": "등록",
#          "country": "KR"
#        }, ...
#      ]
#    }
#
# 4. Notion DB에서 Type=Patent인 항목도 patents 배열로 변환
# 5. data/publications.json에 저장
# 6. (선택) index-standalone.html 재빌드
