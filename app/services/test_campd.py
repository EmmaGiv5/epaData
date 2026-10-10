from pprint import pprint

from services.campd_service import fetch_dataset


def test_hourly_facility():
    result = fetch_dataset(
        dataset="hourly_facility",
        filters={
            "stateCode": "AL|GA|KY|MI",
            "beginDate": "2025-01-01",
            "endDate": "2025-01-02",
        },
        page=1,
        per_page=30,
    )

    print("Total records:", result["total"])
    print("Records returned:", len(result["records"]))

    if result["records"]:
        print("\nFirst record:")
        pprint(result["records"][0])
    else:
        print("No records returned for these filters.")


if __name__ == "__main__":
    test_hourly_facility()
