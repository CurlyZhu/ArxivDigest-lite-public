# encoding: utf-8
import os
import tqdm
from bs4 import BeautifulSoup as bs
import urllib.request
import json


def _download_new_papers(field_abbr):
    NEW_SUB_URL = f'https://arxiv.org/list/{field_abbr}/new'  # https://arxiv.org/list/cs/new
    page = urllib.request.urlopen(NEW_SUB_URL)
    soup = bs(page)
    content = soup.body.find("div", {'id': 'content'})

    # find the first h3 element in content
    h3 = content.find("h3").text   # e.g: New submissions for Wed, 10 May 23
    date = h3.replace("New submissions for", "").strip()

    dt_list = content.dl.find_all("dt")
    dd_list = content.dl.find_all("dd")
    arxiv_base = "https://arxiv.org/abs/"

    assert len(dt_list) == len(dd_list)
    new_paper_list = []
    for i in tqdm.tqdm(range(len(dt_list))):
        paper = {}
        paper_number = dt_list[i].text.strip().split(" ")[2].split(":")[-1]
        paper['main_page'] = arxiv_base + paper_number
        #paper['pdf'] = arxiv_base.replace('abs', 'pdf') + paper_number

        paper['title'] = dd_list[i].find("div", {"class": "list-title mathjax"}).text.replace("Title:", "").strip()
        #paper['authors'] = dd_list[i].find("div", {"class": "list-authors"}).text.replace("Authors:\n", "").replace("\n", "").strip()
        paper['subjects'] = dd_list[i].find("div", {"class": "list-subjects"}).text.replace("Subjects:", "").strip()
        paper['abstract'] = dd_list[i].find("p", {"class": "mathjax"}).text.replace("\n", " ").strip()
        new_paper_list.append(paper)

    return new_paper_list


def get_papers(field_abbr, limit=None):
    results = _download_new_papers(field_abbr)
    return results
