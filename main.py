"""Entry point: print product codes from data/tenderbazar/product.json."""

from scrapers import tenderbazar


def main():
	input_path = "data/tenderbazar/product.json"
	output_path = "data/tenderbazar/tenders.json"
	tenderbazar.collect_all_tenders(input_path=input_path, output_path=output_path)


if __name__ == "__main__":
	main()
