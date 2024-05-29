from collections import Counter
from typing import List, Union, Dict


def parse_groups_to_dict(lines: List[str]) -> Dict[str, Union[dict, str]]:
    """
    Converts a list of hyphen-delimited strings into a nested dictionary.

    This function takes a list of strings, where each string contains substrings
    separated by hyphens ('-'). Each substring becomes a key in a nested dictionary.
    If a substring ends with '?V', the key is set with an empty value ('') instead
    of an empty dictionary.

    :param lines: : A list of strings to be converted into a nested dictionary.
    :return: A nested dictionary representing the structure of the input strings.
    Example:
    >>> ex = [
    ...     "a-b-c?V",
    ...     "a-b-d",
    ...     "a-e"
    ... ]
    >>> parse_groups_to_dict(ex)
    {
        'a': {
            'b': {
                'c': '',
                'd': {}
            },
            'e': {}
        }
    }
    """
    result = dict()
    for line in lines:
        cur_dict = result
        list_line = line.split('-')
        for var in list_line:

            if var.endswith('?V'):
                cur_dict = cur_dict.setdefault('-'.join(list_line).replace('?V', ''), '')
            else:
                cur_dict = cur_dict.setdefault(var, {})

    return result


def parse_vars_to_dict(lines: List[str], path: str) -> dict:
    """
    Parses a list of lines and organizes them into a dictionary based on a specified pattern.
    :param lines: A list of strings representing lines to be parsed.
    :param path : A string representing the pattern to be used for organizing the lines.
    :return dict: A dictionary containing the parsed lines organized according to the specified pattern.

    Example:
        lines = ['x:a-b','x:b-c','x:a-c']
        pattern = 'x'
        result = parse_vars_to_dict(lines, pattern)
        # Output:
        # {
        #   'x:a': {'x:a-b': '', 'x:a-c': ''},
        #   'x:b-c': ''
        # }
    """
    result = {}
    folder_names = [line.split(':')[1].split('-')[0] for line in lines]
    folder_counts = Counter(folder_names)
    for ix, line in enumerate(lines):
        folder = folder_names[ix]
        if folder_counts[folder] > 1:
            key = f'{path}:{folder}'
            if key not in result:
                result[key] = {}
            result[key][line] = ''
        else:
            result[line] = ''

    return result


def parse_search_to_dict(lines: List[str]) -> dict:
    """
    Parses a list of lines representing search strings and organizes them into a dictionary.
    :param lines: A list of strings representing search strings to be parsed.
    :return: A dictionary containing the parsed search strings organized hierarchically.
    """
    result = dict()
    for line in lines:
        list_line = line.replace(':', '-:', 1).split('-')
        cur_dict = result
        for ix in range(len(list_line)):
            if ix == len(list_line) - 1:
                cur_dict = cur_dict.setdefault('-'.join(list_line).replace('-:', ':', 1), '')
            elif list_line[ix][0] == ':':
                cur_dict = cur_dict.setdefault('-'.join(list_line[:ix + 1]).replace('-:', ':'), {})
                cur_dict = cur_dict.setdefault('-'.join(list_line).replace('-:', ':', 1), '')
                break
            else:
                cur_dict = cur_dict.setdefault(list_line[ix], {})

    return result
