"""
Improved Option Extractor with Real Labels

This module provides functions to extract question options with their real labels/text
from questionnaire HTML, supporting various question types.
"""

from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Tag
import re


class ImprovedOptionExtractor:
    """Extract options with real labels from questionnaire HTML"""

    @staticmethod
    def extract_radio_options(div: Tag) -> List[Dict[str, Any]]:
        """Extract radio button options with labels

        Args:
            div: Question div element

        Returns:
            List of option dicts: [{"value": "1", "label": "男"}, ...]
        """
        options = []
        radio_inputs = div.find_all('input', attrs={'type': 'radio'})

        for radio in radio_inputs:
            radio_id = radio.get('id')
            value = radio.get('value')

            if radio_id and value:
                # Find corresponding label
                label_div = div.find('div', attrs={'class': 'label', 'for': radio_id})
                label_text = label_div.get_text(strip=True) if label_div else None

                options.append({
                    "value": value,
                    "label": label_text
                })

        return options

    @staticmethod
    def extract_checkbox_options(div: Tag) -> List[Dict[str, Any]]:
        """Extract checkbox options with labels

        Args:
            div: Question div element

        Returns:
            List of option dicts: [{"value": "1", "label": "电商平台推荐"}, ...]
        """
        options = []
        checkbox_inputs = div.find_all('input', attrs={'type': 'checkbox'})

        for checkbox in checkbox_inputs:
            checkbox_id = checkbox.get('id')
            value = checkbox.get('value')

            if checkbox_id and value:
                # Find corresponding label
                label_div = div.find('div', attrs={'class': 'label', 'for': checkbox_id})
                label_text = label_div.get_text(strip=True) if label_div else None

                options.append({
                    "value": value,
                    "label": label_text
                })

        return options

    @staticmethod
    def extract_select_options(div: Tag) -> List[Dict[str, Any]]:
        """Extract select/dropdown options with labels

        Args:
            div: Question div element

        Returns:
            List of option dicts: [{"value": "1", "label": "18岁以下"}, ...]
        """
        options = []
        select_elem = div.find('select')

        if select_elem:
            for option in select_elem.find_all('option'):
                value = option.get('value')
                label_text = option.get_text(strip=True)

                # Skip placeholder options
                if value and value != '-2' and label_text and label_text != '请选择':
                    options.append({
                        "value": value,
                        "label": label_text
                    })

        return options

    @staticmethod
    def extract_rating_options(div: Tag) -> List[Dict[str, Any]]:
        """Extract rating/Likert scale options with labels

        Args:
            div: Question div element

        Returns:
            List of option dicts: [{"value": "1", "label": "非常不同意"}, ...]
        """
        options = []

        # Find the scale title for labels
        scale_titles = {}
        scale_title_div = div.find('div', class_='scaleTitle')

        if scale_title_div:
            titles = scale_title_div.find_all('div', class_=re.compile('scaleTitle_'))
            if len(titles) == 2:
                scale_titles['min'] = titles[0].get_text(strip=True)
                scale_titles['max'] = titles[1].get_text(strip=True)

        # Find rating links
        rating_links = div.find_all('a', class_=re.compile('rate-off'))

        for link in rating_links:
            val = link.get('val')
            title = link.get('title')

            if val:
                options.append({
                    "value": val,
                    "label": title if title else f"选项 {val}"
                })

        return options

    @staticmethod
    def extract_nps_options(div: Tag) -> List[Dict[str, Any]]:
        """Extract NPS (0-10) scale options with labels

        Args:
            div: Question div element

        Returns:
            List of option dicts: [{"value": "1", "label": "1"}, ...]
        """
        options = []
        rating_links = div.find_all('a', class_=re.compile('rate-off'))

        for link in rating_links:
            val = link.get('val')
            title = link.get('title')

            if val:
                options.append({
                    "value": val,
                    "label": title if title else f"选项 {val}"
                })

        return options

    @staticmethod
    def extract_matrix_column_labels(div: Tag) -> List[Dict[str, Any]]:
        """Extract matrix column headers (scale options)

        Args:
            div: Question div element

        Returns:
            List of column option dicts: [{"value": "1", "label": "非常不关注"}, ...]
        """
        options = []

        # Find table header row
        table = div.find('table', class_=re.compile('matrix'))
        if table:
            header_row = table.find('tr', class_='trlabel')
            if header_row:
                headers = header_row.find_all('th')[1:]  # Skip first empty header

                for idx, header in enumerate(headers, 1):
                    label_text = header.get_text(strip=True)
                    options.append({
                        "value": str(idx),
                        "label": label_text
                    })

        return options

    @staticmethod
    def extract_matrix_row_items(div: Tag) -> List[Dict[str, Any]]:
        """Extract matrix row items (row titles)

        Args:
            div: Question div element

        Returns:
            List of row items: [{"rowid": 1, "title": "价格"}, ...]
        """
        items = []

        table = div.find('table', class_=re.compile('matrix'))
        if table:
            # Find all data rows (not header rows)
            data_rows = table.find_all('tr', attrs={'tp': 'd'})

            for idx, row in enumerate(data_rows, 1):
                # Get row title from first td
                title_td = row.find('td', class_='scalerowtitletd')
                if title_td:
                    title_text = title_td.get_text(strip=True)
                    items.append({
                        "rowid": str(idx),
                        "title": title_text
                    })

        return items

    @staticmethod
    def extract_sort_options(div: Tag) -> List[Dict[str, Any]]:
        """Extract sort question options

        Args:
            div: Question div element

        Returns:
            List of sort option dicts: [{"value": "1", "label": "直接降价"}, ...]
        """
        options = []

        # Find all sort items
        sort_items = div.find_all('li', class_='ui-li-static')

        for item in sort_items:
            serial = item.get('serial')
            span = item.find('span')
            label_text = span.get_text(strip=True) if span else None

            if serial and label_text:
                options.append({
                    "value": serial,
                    "label": label_text
                })

        return options

    @staticmethod
    def extract_weight_allocation_items(div: Tag) -> List[Dict[str, Any]]:
        """Extract weight allocation question items

        Args:
            div: Question div element

        Returns:
            List of items: [{"rowid": 1, "title": "菜品口味"}, ...]
        """
        items = []

        table = div.find('table', class_=re.compile('matrix'))
        if table:
            # Find all rows with input[issum="1"]
            input_with_issum = table.find_all('input', attrs={'issum': '1'})

            for input_elem in input_with_issum:
                rowid = input_elem.get('rowid')

                if rowid:
                    # Find title in row
                    title_td = input_elem.find_parent('tr').find('td', class_='title')
                    if not title_td:
                        title_td = input_elem.find_parent('tr').find('td', class_='scalerowtitletd')

                    title_text = title_td.get_text(strip=True) if title_td else None

                    items.append({
                        "rowid": rowid,
                        "title": title_text
                    })

        return items
