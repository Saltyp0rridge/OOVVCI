import json
import os
import numpy as np
import openai
from src.utility import GPT, Task_UI_grounding_prompt, get_top_combined_similarities, plan_prompt, process_action_info
openai.api_key = os.getenv('OPENAI_API_KEY')


class Evaluate():

    def __init__(self, model):
        self.model = model
        self.score = []
        self.reason = []
        self.weights = []

    @staticmethod
    def log_decorator(func):
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            self.model.log_json["@Previous_Step"] = self.model.current_path_str
            self.model.log_json["@Action"] = self.model.current_action
            self.model.log_json["@Module"].append({
                "Name": "Evaluate",
                "Description": "This module is an evaluation module, evaluating the selected components of their contribution to fulfilling the user's intent",
                "Output": {key: item for key, item in zip(list(
                    filter(lambda x: "id=" in x, self.model.screen.semantic_info_list)), self.score)},
            })

            with open("logs/log{}.json".format(self.model.index), "w", encoding="utf-8") as f:
                json.dump(self.model.log_json, f, indent=4)
            print("node_selected", self.model.node_selected)
            print("node_selected_id", self.model.node_selected_id)
            print(self.model.final_node.generate_all_semantic_info())
            return result
        return wrapper

    @log_decorator
    def evaluate(self, ACTION_TRACE):
        self.score_comp(ACTION_TRACE)
        self.select_top_one()
        return self.score

    def score_comp(self, ACTION_TRACE):
        task, knowledge = self.model.Selection_KB.find_experiences(
            query=[self.model.task, self.model.screen.page_description])
        resp = GPT(Task_UI_grounding_prompt(self.model.task, ACTION_TRACE["ACTION"], self.model.similar_tasks,
                                            self.model.similar_traces, self.model.predicted_step, self.model.screen.semantic_info_list, self.model.predict_module.comp_json, knowledge))
        
        # self.score, self.reason = np.array(resp["score"])/10, resp["reason"]
        scores = [1.0 for x in self.model.screen.semantic_info_list if 'id=' in x]
        for key, rating in resp.items():
            if key.startswith('id_'):
                idx = int(key[len('id_'):]) - 1
                scores[idx] = rating
        self.score, self.reason = np.array(scores) / 10, ["unknown"] * len(scores)
        
        self.model.candidate_str = [item for index, item in enumerate(self.model.screen.semantic_info_list) if index in [
            i for i, score in enumerate(self.score) if score > 3.0] and "id=" in item]
        if self.weights == []:
            self.weights = [1] * len(self.score)
        self.score = np.exp(self.score) / np.sum(np.exp(self.score))
        print(self.score)
        print(self.weights)
        self.score = (self.score * np.array(self.weights)
                      ).tolist() if self.weights != [] else self.score
        print(self.score)

    def select_top_one(self):
        top_index = np.argmax(self.score)
        self.model.node_selected = list(filter(
            lambda x: "id="+str(top_index+1) in x, self.model.screen.semantic_info_list))[0]
        response = GPT(plan_prompt(self.model.task,
                                   self.model.page_description, self.model.node_selected))
        self.model.node_selected_action, self.model.node_selected_text = response.get(
            "action"), response.get("text")
        self.model.node_selected_id = int(
            self.model.node_selected.split("id=")[1].split(" ")[0])
        self.model.current_action = process_action_info(
            self.model.node_selected_action, self.model.node_selected_text, self.model.node_selected)
        self.model.current_path.append(self.model.current_action)

        self.model.final_node = self.model.screen.semantic_nodes["nodes"][self.model.screen.semantic_info_list.index(
            self.model.node_selected)]

    def update_weights(self, weights):
        w = [0]*len(list(
            filter(lambda x: "id=" in x, self.model.screen.semantic_info_list)))
        for key, item in weights.items():
            if key.startswith("id_"):
                index = int(key.split("_")[1]) - 1
                w[index] = int(item)
        self.weights = (np.array(self.weights) *
                        np.array([(10-i)/10 for i in w])).tolist()
