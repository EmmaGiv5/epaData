from app import create_app
from machine_learning.training import train_all


if __name__ == "__main__":
    app = create_app()

    with app.app_context():
        print("\nTraining baseline, Ridge, and random forest models...")
        summaries = train_all()

        print(f"\n{'Model':<22}{'Val MAE':>14}{'Test MAE':>14}{'Test RMSE':>14}{'Test R2':>10}")
        for item in summaries:
            val, test = item["metrics"]["validation"], item["metrics"]["test"]
            print(
                f"{item['label']:<22}{val['mae']:>14,.0f}{test['mae']:>14,.0f}"
                f"{test['rmse']:>14,.0f}{test['r2']:>10.3f}"
            )
        persistence = summaries[0]["persistence"]["test"]
        print(
            f"{'Persistence reference':<22}{'':>14}{persistence['mae']:>14,.0f}"
            f"{persistence['rmse']:>14,.0f}{persistence['r2']:>10.3f}"
        )
        print("\nModels saved to saved_models/")