import json
from src.utility import add_son_to_father, add_value_to_html_tag
import copy
import random
import os
import re
import openai
import tqdm

from src.utility import GPT, UI_grounding_prompt, task_grounding_prompt

openai.api_key = os.getenv('OPENAI_API_KEY')


class Predict():

    def __init__(self, model, pagejump):
        self.pagejump_KB = pagejump
        self.model = model
        self.modified_result = None
        self.insert_prompt = None

    def log_decorator(func):
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            self.model.log_json["@Page_description"] = self.model.page_description
            self.model.log_json["@Similar_tasks"] = [j+":"+"=>".join(
                k) for j, k in zip(self.model.similar_tasks, self.model.similar_traces)]
            self.model.log_json["@Module"].append({
                "Name": "Predict",
                "Description": "This module is a prediction model, predicting what will appear after clicking each components on current screen",
                "Output": self.comp_json
            })
            if not os.path.exists("logs/log{}.json".format(self.model.index)):
                os.mkdir("logs/log{}.json".format(self.model.index))
                with open("logs/log{}.json".format(self.model.index), "w") as f:
                    json.dump(self.model.log_json, f, indent=4)
            return result
        return wrapper

    def Task_grounding(self):
        result = GPT(task_grounding_prompt(self.model.task,
                     self.model.similar_tasks, self.model.similar_traces))
        self.model.predicted_step = result["result"]
        print("predicted_step", self.model.predicted_step)

    def UI_grounding(self):
        SEMANTIC_INFO = self.model.screen.semantic_info_list
        SEMANTIC_STR = self.model.screen.semantic_info_str
        self.current_comp = SEMANTIC_INFO
        self.next_comp = [""]*len(SEMANTIC_INFO)
        self.comp_json = dict.fromkeys(
            SEMANTIC_INFO, [])
        predict_node = copy.deepcopy(
            SEMANTIC_INFO)
        for i in tqdm.tqdm(range(len(SEMANTIC_INFO))):
            res = self.query(SEMANTIC_STR, SEMANTIC_INFO[i])
            if res:
                self.next_comp[i] = {"description": "", "comp": res}
                self.comp_json[SEMANTIC_INFO[i]] = {
                    "description": "", "comp": res}
                predict_node[i] = "None"
        response_text = GPT(UI_grounding_prompt(
            list(filter(lambda x: x != "None", predict_node))))
        self.model.page_description = response_text["Page"]
        self.model.current_path.append("Page:"+self.model.page_description)
        for key, value in response_text.items():
            if key.startswith("id_"):
                index = int(key.split("_")[1]) - 1
                self.next_comp[index] = value
                self.comp_json[SEMANTIC_INFO[index]] = value
        self.model.extended_info = add_son_to_father(
            [add_value_to_html_tag(
                key, value["description"]) for key, value in self.comp_json.items()], self.model.screen.trans_relation)

    @log_decorator
    def predict(self):
        self.Task_grounding()
        self.UI_grounding()

    def query(self, page, node):
        """
        #TODO：Queries the knowledge from KB
        """
        res = self.pagejump_KB.find_next_page(page, node)
        if res != []:
            res = res[0].split("\\n")
            res = [re.sub(r'id=\d+', '', s) for s in res]
            return res
        else:
            return None
