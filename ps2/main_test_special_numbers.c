#include <stdio.h>
int special_numbers(const int input_array[], const int array_size, int result_array[]);
int main() {
    int arr[6] = {16, 17, 4, 3, 5, 2};
    int result[6] = {0};
    int count = special_numbers(arr, 6, result);
    if (count == 2 && result[0] == 17 && result[1] == 5) {
        printf("TASK:special_numbers=1\n");
    } else {
        printf("TASK:special_numbers=0\n");
    }
    return 0;
}
