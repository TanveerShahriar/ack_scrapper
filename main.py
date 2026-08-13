"""Entry point: print product codes from data/tenderbazar/product.json."""

from scrapers import tenderbazar


def main():
	input_path = "data/tenderbazar/product.json"
	output_path = "data/tenderbazar/tenders.json"
	summary = tenderbazar.collect_all_tenders(input_path=input_path, output_path=output_path)

	# send notifications if there are updates
	try:
		from notifications import email as notifier
		sent = notifier.send_update_notifications(summary)
		if sent:
			print("Notification email sent to users.")
		else:
			print("No notification sent (no updates or no recipients configured).")
	except Exception:
		print("Notifier failed or missing; skipping email send.")


if __name__ == "__main__":
	main()
