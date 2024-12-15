import pandas as pd
import os
import constants

def create_new_dataset(input_folder, output_folder, threshold):
    # Keep track of the files that have not been processed
    unprocessed_files = []
    for filename in os.listdir(input_folder):
        file_path = os.path.join(input_folder, filename)
        data = pd.read_csv(file_path)

        try:
            filtered_data = data[data['pmi'] > threshold]
        except KeyError:
            print(f"KeyError: 'pmi' column not found in {file_path}")
            unprocessed_files.append(filename)
            continue
        output_path = os.path.join(os.path.join(output_folder, str(threshold)), filename)
        filtered_data.to_csv(output_path, index=False)

        print(f"Filtered data saved to {output_path}")
    if (len(unprocessed_files) > 0):
        print(f"Files that were not processed: {unprocessed_files}")


if __name__ == "__main__":
    input_folder = constants.CATEGORY
    output_folder = constants.PMI_SCORES
    threshold = 0.1
    create_new_dataset(input_folder, output_folder, threshold)

    print("Done!")
