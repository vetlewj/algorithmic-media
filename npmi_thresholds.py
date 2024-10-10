import pandas as pd
import os

import constants


def create_new_dataset(input_folder, output_folder, threshold):
    for filename in os.listdir(input_folder):
        file_path = os.path.join(input_folder, filename)
        data = pd.read_csv(file_path)

        filtered_data = data[data['pmi'] > threshold]

        output_filename = f"{filename}_{str(threshold)}"
        output_path = os.path.join(output_folder, output_filename)
        filtered_data.to_csv(output_path, index=False)

        print(f"Filtered data saved to {output_path}")


if __name__ == "__main__":
    input_folder = constants.DATA
    output_folder = constants.PMI_SCORES
    threshold = 0.1
    create_new_dataset(input_folder, output_folder, threshold)

    print("Done!")
