import logging
import requests
import argparse
from tqdm import tqdm
from title_annotator.base_objects import ChunkImport, RatingRequestNew
from tools.common import chunk_to_rating_request

logging.basicConfig(level=logging.INFO)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load JSONL file with chunks, transform each to RatingRequestNew and send it to appliction API.")
    parser.add_argument("--input-file", "-i", type=str, required=True,
                        help="Path to the input JSONL file containing chunks.")
    parser.add_argument("--api-endpoint", "-a", type=str, required=True,
                        help="API endpoint to send the rating requests to.")
    return parser.parse_args()


def create_api_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        'Content-Type': 'application/json'
    })
    return session


def send_rating_request(session: requests.Session, api_endpoint: str, rating_request: RatingRequestNew):
    url = f"{api_endpoint}/api/rating/request"
    response = session.post(url, json=rating_request.model_dump())
    if response.status_code != 200:
        logging.error(f"Failed to send rating request {rating_request.id}: {response.status_code} {response.text}")
        raise Exception(f"Failed to send rating request {rating_request.id}: {response.status_code} {response.text}")
    logging.info(f"Successfully sent rating request {rating_request.id}")


def main():
    args = parse_args()

    session = create_api_session()

    with open(args.input_file, 'r', encoding='utf-8') as f:
        for line in tqdm(f, desc="Processing chunks"):
            chunk_data = line.strip()
            if not chunk_data:
                continue
            chunk = ChunkImport.model_validate_json(chunk_data)
            rating_request = chunk_to_rating_request(chunk)
            send_rating_request(session, args.api_endpoint, rating_request)
    logging.info("All rating requests have been sent.")


if __name__ == "__main__":
    main()
