import concurrent.futures
import re

from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify
from tclogger import logger
from termcolor import colored

from constants import IGNORE_TAGS, IGNORE_CLASSES, IGNORE_WORDS


class HTMLPurifier:
    def __init__(self, verbose=False, output_format="markdown"):
        self.verbose = verbose
        self.output_format = output_format

    def html_to_markdown(self, html_str):
        markdown_str = markdownify(
            html_str, strip=["a"], wrap_width=120, heading_style="ATX"
        )
        self.markdown_str = re.sub(r"\n{3,}", "\n\n", markdown_str)

        return self.markdown_str

    def filter_elements_from_html(self, html_str):
        soup = BeautifulSoup(html_str, "html.parser")
        removed_element_counts = 0
        for element in soup.find_all():
            class_str = ""
            id_str = ""
            try:
                class_attr = element.get("class", [])
                if class_attr:
                    class_str = " ".join(list(class_attr))
                if id_str:
                    class_str = f"{class_str} {id_str}"
            except:
                pass

            try:
                id_str = element.get("id", "")
            except:
                pass

            is_class_in_ignore_classes = any(
                re.search(ignore_class, class_str, flags=re.IGNORECASE)
                for ignore_class in IGNORE_CLASSES
            )
            is_id_in_ignore_classes = any(
                re.search(ignore_class, id_str, flags=re.IGNORECASE)
                for ignore_class in IGNORE_CLASSES
            )

            if (
                (not element.text.strip())
                or (element.name in IGNORE_TAGS)
                or is_class_in_ignore_classes
                or is_id_in_ignore_classes
            ):
                element.decompose()
                removed_element_counts += 1

        logger.mesg(
            f"  - Elements: "
            f'{colored(len(soup.find_all()),"light_green")} (Remained) / {colored(removed_element_counts,"light_red")} (Removed)'
        )

        return str(soup)

    def read_html_file(self, html_path):
        logger.note(f"> Purifying content in: {html_path}")

        if not Path(html_path).exists():
            warn_msg = f"File not found: {html_path}"
            logger.warn(warn_msg)
            raise FileNotFoundError(warn_msg)

        encodings = ["utf-8", "latin-1"]
        for encoding in encodings:
            try:
                with open(html_path, "r", encoding=encoding, errors="ignore") as rf:
                    html_str = rf.read()
                    return html_str
            except UnicodeDecodeError:
                pass
        else:
            warn_msg = f"No matching encodings: {html_path}"
            logger.warn(warn_msg)
            raise UnicodeDecodeError(warn_msg)

    def purify_file(self, html_path, filter_elements=True):
        logger.enter_quiet(not self.verbose)
        html_str = self.read_html_file(html_path)
        if not html_str:
            return ""
        else:
            result = self.purify_str(html_str, filter_elements=filter_elements)
        logger.exit_quiet(not self.verbose)
        return result

    def purify_str(self, html_str, filter_elements=True):
        logger.enter_quiet(not self.verbose)
        if not html_str:
            return ""

        if filter_elements:
            html_str = self.filter_elements_from_html(html_str)

        if self.output_format == "markdown":
            markdown_str = self.html_to_markdown(html_str)

            for ignore_word in IGNORE_WORDS:
                markdown_str = re.sub(
                    ignore_word, "", markdown_str, flags=re.IGNORECASE
                )
            result = markdown_str.strip()
        else:
            result = html_str.strip()

        logger.exit_quiet(not self.verbose)
        return result


class BatchHTMLPurifier:
    def __init__(self, verbose=False, output_format="markdown"):
        self.html_path_and_purified_content_list = []
        self.done_count = 0
        self.verbose = verbose
        self.output_format = output_format

    def purify_single_html_file(self, html_path):
        purifier = HTMLPurifier(verbose=self.verbose, output_format=self.output_format)
        purified_content = purifier.purify_file(html_path)
        self.html_path_and_purified_content_list.append(
            {"path": html_path, "str": purified_content, "format": self.output_format}
        )
        self.done_count += 1

        if self.verbose:
            logger.success(
                f"> [{self.done_count}/{self.total_count}] purified of [{html_path}]"
            )

    def purify_files(self, html_paths):
        self.html_path = html_paths
        self.total_count = len(self.html_path)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self.purify_single_html_file, html_path)
                for html_path in self.html_path
            ]
            for idx, future in enumerate(concurrent.futures.as_completed(futures)):
                result = future.result()

        return self.html_path_and_purified_content_list


def purify_html_file(html_path, verbose=False, output_format="markdown"):
    purifier = HTMLPurifier(verbose=verbose, output_format=output_format)
    return purifier.purify_file(html_path)


def purify_html_str(html_str, verbose=False, output_format="markdown"):
    purifier = HTMLPurifier(verbose=verbose, output_format=output_format)
    return purifier.purify_str(html_str)


def purify_html_files(html_paths, verbose=False, output_format="markdown"):
    batch_purifier = BatchHTMLPurifier(verbose=verbose, output_format=output_format)
    return batch_purifier.purify_files(html_paths)


if __name__ == "__main__":
    html_root = Path(__file__).parent / "samples"
    html_paths = list(html_root.glob("*.html"))
    html_path_and_purified_content_list = purify_html_files(
        html_paths, output_format="html"
    )
    for item in html_path_and_purified_content_list:
        html_path = item["path"]
        purified_content = item["str"]
        logger.file(html_path)
        logger.line(purified_content)
