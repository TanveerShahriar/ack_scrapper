"""Main entry point for project scrapers."""

from scrapers import bbtender, tenderbazar


def main():
	print("Running Bangladesh Bank tender sync...")
	summary = bbtender.sync_tenders(path="data/bbtender/tender.json", send_email=True)
	print(f"Bangladesh Bank sync status: updated={summary['updated']}, new={summary['new_count']}")

	# Existing TenderBazar flow can be enabled here when needed
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
