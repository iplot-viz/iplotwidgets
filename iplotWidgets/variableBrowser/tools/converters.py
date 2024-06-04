from typing import List
import pandas as pd


def parse_groups_to_dict(lines: List) -> dict:
    result = dict()
    for line in lines:
        cur_dict = result
        list_line = line.split('-')
        for var in list_line:
            if var.endswith('?V'):
                cur_dict = cur_dict.setdefault('-'.join(list_line), '')
            else:
                cur_dict = cur_dict.setdefault(var, {})

    return result


def parse_vars_to_dict(lines: List, pattern: str) -> dict:
    result = {}
    folders = [line.split(':')[1].split('-')[0] for line in lines]
    for ix in range(len(lines)):
        if folders.count(folders[ix]) > 1:
            key = f'{pattern}:{folders[ix]}'
            if key not in result:
                result[key] = {}
            result[key][lines[ix] + '?V'] = ''
        else:
            result.update({lines[ix] + '?V': ''})

    return result


def parse(lines) -> dict:
    result = dict()
    for line in lines:
        list_line = line.replace(':', '-:', 1).split('-')
        cur_dict = result
        for ix in range(len(list_line)):
            if ix == len(list_line) - 1:
                cur_dict = cur_dict.setdefault('-'.join(list_line).replace('-:', ':', 1) + "?V", '')
            elif list_line[ix][0] == ':':
                cur_dict = cur_dict.setdefault('-'.join(list_line[:ix + 1]).replace('-:', ':'), {})
                cur_dict = cur_dict.setdefault('-'.join(list_line).replace('-:', ':', 1) + "?V", '')
                break
            else:
                cur_dict = cur_dict.setdefault(list_line[ix], {})

    return result


def parse_pulses(lines: List) -> dict:
    result = dict()

    for line in lines:
        result[line.pulseID] = {'description': line.description,
                                'status': line.status.strip(),
                                'timeFrom': pd.to_datetime(line.timeFrom),
                                'timeTo': pd.to_datetime(line.timeTo),
                                'duration': pd.to_datetime(line.timeTo) - pd.to_datetime(line.timeFrom)}

    return result
