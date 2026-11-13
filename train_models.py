from app import create_app

from machine_learning.train_model_one import train_model_one
from machine_learning.train_model_two import train_model_two


if __name__ == "__main__":

    app = create_app()

    with app.app_context():

        print("\nTraining Model 1: Predictions...")

        result_one = train_model_one()
        print(result_one)

        print("\nTraining Model 2: Sensitivity Analysis...")

        result_two = train_model_two()
        print(result_two)

        print("\nBoth models have been trained successfully!")