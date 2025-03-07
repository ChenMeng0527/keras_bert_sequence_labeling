# -*- coding: utf-8 -*-
# @Time : 2021/1/9 11:18
# @Author : Jclian91
# @File : tf_serving_normal_predict_test.py
# @Place : Yangpu, Shanghai

'''
1：读取文本数据
2：讲文本数据转为batch，然后对于每个batch进行token
3: batch放入接口中预测
'''

import json
import requests
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
from keras_bert import Tokenizer


# 读取label2id字典
with open("../example_label2id.json", "r", encoding="utf-8") as h:
    label_id_dict = json.loads(h.read())

id_label_dict = {v: k for k, v in label_id_dict.items()}


# 载入数据

# 对vocab中的词进行index处理
dict_path = '../chinese_L-12_H-768_A-12/vocab.txt'
token_dict = {}
with open(dict_path, 'r', encoding='utf-8') as reader:
    for line in reader:
        token = line.strip()
        token_dict[token] = len(token_dict)


class OurTokenizer(Tokenizer):
    def _tokenize(self, text):
        '''
        如果字不在就用unk代替
        :param text:
        :return:
        '''
        R = []
        for c in text:
            if c in self._token_dict:
                R.append(c)
            else:
                R.append('[UNK]')
        return R


# 将BIO序列转化为JSON格式
def bio_to_json(string, tags):
    '''

    :param string:
    :param tags:
    :return:
    '''
    item = {"string": string, "entities": []}
    entity_name = ""
    entity_start = 0
    iCount = 0
    entity_tag = ""

    for c_idx in range(min(len(string), len(tags))):
        c, tag = string[c_idx], tags[c_idx]
        if c_idx < len(tags)-1:
            tag_next = tags[c_idx+1]
        else:
            tag_next = ''

        if tag[0] == 'B':
            entity_tag = tag[2:]
            entity_name = c
            entity_start = iCount
            if tag_next[2:] != entity_tag:
                item["entities"].append({"word": c, "start": iCount, "end": iCount + 1, "type": tag[2:]})
        elif tag[0] == "I":
            if tag[2:] != tags[c_idx-1][2:] or tags[c_idx-1][2:] == 'O':
                tags[c_idx] = 'O'
                pass
            else:
                entity_name = entity_name + c
                if tag_next[2:] != entity_tag:
                    item["entities"].append({"word": entity_name, "start": entity_start, "end": iCount + 1, "type": entity_tag})
                    entity_name = ''
        iCount += 1
    return item


tokenizer = OurTokenizer(token_dict)


# 读取测试样本
with open("tf_test_sample.txt", "r", encoding="utf-8") as f:
    content = [_.strip() for _ in f.readlines()]

batch_size = 10
start_time = time.time()

global predict_result
predict_result = []


# 测试HTTP响应时间
def get_predict(i, sentence_list):
    '''


    :param i:
    :param sentence_list:
    :return:
    '''
    tensor = {"instances": []}
    for sentence in sentence_list:
        token_ids, segment_is = tokenizer.encode(sentence, max_len=128)
        tensor["instances"].append({"input_1": token_ids,
                                    "input_2": segment_is})

    url = "http://192.168.1.193:8561/v1/models/example_ner:predict"
    req = requests.post(url, json=tensor)
    if req.status_code == 200:
        for j in range(len(req.json()['predictions'])):
            t = np.asarray(req.json()['predictions'][j]).argmax(axis=1)
            tags = [id_label_dict[_] for _ in t]
            print("predict {} batch, batch no {}".format(i, j))
            predict_result.append(bio_to_json(sentence_list[j], tags[1:-1]))


# 批量调用测试
for i in range(len(content)//batch_size):
    get_predict(i, content[batch_size*i:batch_size*(i+1)])

end_time = time.time()
print("avg cost time: {}".format((end_time-start_time)/len(content)))

with open("batch_predict.json", "w", encoding="utf-8") as g:
    g.write(json.dumps(predict_result, ensure_ascii=False, indent=2))