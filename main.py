import json
from typing import List, Optional, Dict

import uvicorn
from fastapi import FastAPI, Request, Depends
from pydantic import BaseModel
from contextlib import asynccontextmanager
import re


class LawLink(BaseModel):
    law_id: Optional[int] = None
    article: Optional[str] = None
    point_article: Optional[str] = None
    subpoint_article: Optional[str] = None


class LinksResponse(BaseModel):
    links: List[LawLink]


class TextRequest(BaseModel):
    text: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    with open("law_aliases.json", "r") as file:
        codex_aliases = json.load(file)
    
    app.state.codex_aliases = codex_aliases
    print("🚀 Сервис запускается...")

    # подготовка изначальных регулярных выражений
    sub_points = r"подпункт[А-Яа-яA-Za-z]*|пп\.|подп\."
    points     = r"пункт[А-Яа-яA-Za-z]*|п\.|ч\.|часть[А-Яа-яA-Za-z]*"
    articles   = r"стать[А-Яа-яA-Za-z]*|ст\."

    numbers = r"\d+\.*\d*"
    letters = r"[А-Оа-оA-Za-z]?[А-Оа-оA-Za-z]"

    indexes = fr"{numbers}\s*,*\s*|{letters}\s*,*\s*"

    # Подготовка названий документов
    all_laws = ''
    all_laws_ids = dict()

    for k in codex_aliases.keys():
        law = codex_aliases[k]
        for alias_ in law:
            all_laws += re.escape(alias_) + '|'
            all_laws_ids[alias_] = k
        
    all_laws = '(' + all_laws[:-1] + ')'

    # Подготовка доп рег выражений для парсинга различных вариаций индексов
    pattern_attributes = r""
    pattern_attributes += fr"(?P<sub_points>(?:{sub_points})\s*)(?P<sub_index>(?:{indexes}\s*(?:,\s*|и\s*)?)+)"
    pattern_attributes += fr"(?:(?:(?:и\s+)?))?"
    pattern_attributes += fr"(?:(?P<points>(?:{points})\s*)(?P<point_index>(?:{indexes}\s*(?:,\s*|и\s*)?)+))?"
    pattern_attributes += fr"(?:(?:(?:и\s+)?))?"
    pattern_attributes += fr"(?:(?P<articles>(?:{articles})\s*)(?P<article_index>(?:{indexes}\s*(?:,\s*|и\s*)?)+))?"

    pattern_attributes_2 = r""
    pattern_attributes_2 += fr"(?P<points>(?:{points})\s*)(?P<point_index>(?:{indexes}\s*(?:,\s*|и\s*)?)+)"
    pattern_attributes_2 += fr"(?:(?:(?:и\s+)?))?"
    pattern_attributes_2 += fr"(?:(?P<articles>(?:{articles})\s*)(?P<article_index>(?:{indexes}\s*(?:,\s*|и\s*)?)+))?"

    pattern_attributes_3 = r""
    pattern_attributes_3 += fr"(?P<articles>(?:{articles})\s*)(?P<article_index>(?:{indexes}\s*(?:,\s*|и\s*)?)+)"

    rx = re.compile(pattern_attributes, re.IGNORECASE)
    rx_2 = re.compile(pattern_attributes_2, re.IGNORECASE)
    rx_3 = re.compile(pattern_attributes_3, re.IGNORECASE)

    app.state.all_laws = all_laws
    app.state.all_laws_ids = all_laws_ids
    app.state.rx = rx
    app.state.rx_2 = rx_2
    app.state.rx_3 = rx_3

    yield
    # Shutdown
    del codex_aliases
    print("🛑 Сервис завершается...")

def get_links(rx, rx_2, rx_3, text, all_laws, all_laws_ids):

    pointer = 0

    law_link_list = []

    # подпункт -> пункт | часть -> статья -> название закона/документа

    while pointer < len(text):

        match_law = re.search(all_laws, text[pointer:])

        # print(match_law)
        
        if match_law:
            span_ = match_law.span()
            span_start = span_[0]
            span_end = span_[1]

            substr_start = min(len(text[pointer:][:span_start]), 100)

            substring_ = text[pointer:][span_start - substr_start :span_start]

            # print(substring_, match_law.group(0))

            match_1 = re.search(rx, substring_)
            if match_1:
                pointer += span_end

                subpoint_article = match_1['sub_index']
                if subpoint_article:
                    subpoint_article = subpoint_article.replace(',', '').replace('и', '').split()
                else:
                    subpoint_article = [None]
                point_article = match_1['point_index']
                if point_article:
                    point_article = point_article.replace(',', '').replace('и', '').split()
                else:
                    point_article = [None]
                article = match_1['article_index']
                if article:
                    article = article.replace(',', '').replace('и', '').split()
                else:
                    article = [None]

                for s in subpoint_article:
                    for p in point_article:
                        for a in article:
                            law_link = LawLink()
                            law_link.law_id = all_laws_ids[match_law.groups(0)[0]]

                            law_link.article = a
                            law_link.point_article = p
                            law_link.subpoint_article = s

                            law_link_list.append(law_link)

                continue

            match_2 = re.search(rx_2, substring_)
            if match_2:
                pointer += span_end

                subpoint_article = None
                point_article = match_2['point_index']
                if point_article:
                    point_article = point_article.replace(',', '').replace('и', '').split()
                else:
                    subpoint_article = [None]
                article = match_2['article_index']
                if article:
                    article = article.replace(',', '').replace('и', '').split()
                else:
                    article = [None]

                for p in point_article:
                    for a in article:
                        law_link = LawLink()
                        law_link.law_id = all_laws_ids[match_law.groups(0)[0]]

                        law_link.article = a
                        law_link.point_article = p
                        law_link.subpoint_article = None

                        law_link_list.append(law_link)

                continue

            match_3 = re.search(rx_3, substring_)
            if match_3:
                pointer += span_end

                subpoint_article = None
                point_article = None
                article = match_3['article_index']
                if article:
                    article = article.replace(',', '').replace('и', '').split()
                else:
                    article = [None]

                for a in article:
                    law_link = LawLink()
                    law_link.law_id = all_laws_ids[match_law.groups(0)[0]]

                    law_link.article = a
                    law_link.point_article = None
                    law_link.subpoint_article = None

                    law_link_list.append(law_link)

                continue

            pointer += span_end
            # print(pointer)

            # print('////////')
            
        else:
            pointer = len(text) + 1
    
    return law_link_list

def get_codex_aliases(request: Request) -> Dict:
    return request.app.state.codex_aliases


app = FastAPI(
    title="Law Links Service",
    description="Cервис для выделения юридических ссылок из текста",
    version="1.0.0",
    lifespan=lifespan
)


@app.post("/detect")
async def get_law_links(
    data: TextRequest,
    request: Request,
    codex_aliases: Dict = Depends(get_codex_aliases),
    ) -> LinksResponse:
    """
    Принимает текст и возвращает список юридических ссылок
    """
    # Место для алгоритма распознавания ссылок
    text_length = len(data.text)

    all_laws = request.app.state.all_laws
    all_laws_ids = request.app.state.all_laws_ids
    rx = request.app.state.rx
    rx_2 = request.app.state.rx_2
    rx_3 = request.app.state.rx_3

    link_list = get_links(rx, rx_2, rx_3, data.text, all_laws, all_laws_ids)

    print(codex_aliases["1"])

    return LinksResponse(links=link_list)


@app.get("/health")
async def health_check():
    """
    Проверка состояния сервиса
    """
    return {"status": "healthy"}



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8978)
