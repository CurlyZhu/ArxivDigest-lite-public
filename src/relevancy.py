import logging
import time
import json
import os
import io
import random
import re
import math
import string
from datetime import datetime
import sys

import numpy as np
import tqdm
from openai import OpenAI, OpenAIError


def encode_prompt(prompt_papers):
    """Encode multiple papers into a single formatted string."""
    prompt = ""
    for idx, task_dict in enumerate(prompt_papers):
        (title, abstract) = task_dict["title"], task_dict["abstract"]
        if not title:
            print(f'paper {idx} metadata might be broken.')
        prompt += f"###\n"
        prompt += f"Title: {title}\n"
        prompt += f"Abstract: {abstract}\n"
    prompt += f"\nGenerate response:\n"
    return prompt


def openai_completion(
    client,
    prompt,
    model_name="gpt-4-turbo",
    max_tokens=1800,
    temperature=0.1,
    top_p=1.0,
    n=1,
    sleep_time=2,
):
    """
    Call OpenAI API to process the input.

    Args:
        prompt: formatted input instances, generated as a batch from encode_prompt().
        model_name: Model name. See https://platform.openai.com/docs/models/overview.
        sleep_time: Time to sleep once the rate-limit is hit.

    Returns:
        A completion from OpenAI API's response, formatted as a '\n'-separated string.
    """
    is_chat_model = "gpt-3.5" in model_name or "gpt-4" in model_name

    completions = []
    try:
        if is_chat_model:
            completion_batch = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": open("src/relevancy_prompt.txt").read() + "\n"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                n=n,
            )
        else:
            raise RuntimeError("This LLM has not been supported in this version.")

        choices = completion_batch.choices[0].message.content
        #print(choices)
        completions.append(choices)
    except OpenAIError as e:
        logging.warning(f"OpenAIError: {e}.")
        time.sleep(sleep_time)

    #print(completions)
    return '\n'.join(completions)


def post_process_chat_gpt_response(paper_data, response):
    '''Collecting and post-processing the API response'''
    selected_data = []
    if response is None:
        return []
    json_items = response.replace("\n\n", "\n").split("\n")
    pattern = r"\\[^\"\'bfnrtu\\]"
    try:
        score_items = [
            json.loads(re.sub(pattern, "", line))
            for line in json_items if "score" in line.lower()]
    except Exception:
        raise RuntimeError("failed")
    #print(score_items)
    scores = []
    for item in score_items:
        temp = item["score"]
        if isinstance(temp, str) and "/" in temp:
            scores.append(int(temp.split("/")[0])) # probably for things like "9/10"?
        else:
            scores.append(int(temp))
    if len(score_items) != len(paper_data):
        score_items = score_items[:len(paper_data)]
        hallucination = True
    else:
        hallucination = False

    for idx, inst in enumerate(score_items):
        for key, value in inst.items():
            paper_data[idx][key] = value
        selected_data.append(paper_data[idx])
    return selected_data, hallucination


def process_subject_fields(subjects):
    all_subjects = subjects.split(";")
    all_subjects = [s.split(" (")[0] for s in all_subjects]
    return all_subjects


def generate_relevance_score(
    client,
    all_papers,
    model_name="gpt-4-turbo",
    num_paper_in_prompt=8,
    temperature=0.1,
    top_p=1.0,
    sorting=True
):
    '''Putting the steps together and generate the output for a batch'''
    ans_data = []
    hallucination = False
    for id in tqdm.tqdm(range(0, len(all_papers), num_paper_in_prompt)):
        prompt_papers = all_papers[id:id+num_paper_in_prompt]
        prompt = encode_prompt(prompt_papers)

        request_start = time.time()
        response = openai_completion(
            client=client,
            prompt=prompt,
            model_name=model_name,
            temperature=temperature,
            n=1,
            max_tokens=256*num_paper_in_prompt,
            top_p=top_p,
        )
        #print ("response", response)
        request_duration = time.time() - request_start

        process_start = time.time()
        batch_data, hallu = post_process_chat_gpt_response(prompt_papers, response)
        hallucination = hallucination or hallu
        ans_data.extend(batch_data)

        print(f"\nRequest took {request_duration:.2f}s")
        print(f"Post-processing took {time.time() - process_start:.2f}s")
        print()

    if sorting:
        ans_data = sorted(ans_data, key=lambda x: int(x["score"]), reverse=True)
    
    return ans_data, hallucination
