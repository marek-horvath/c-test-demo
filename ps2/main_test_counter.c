#include <stdio.h>
void counter(const int input_array[], const int arrays_size, int result_array[2]);
int main() {
    int arr[6] = {1, 2, 3, 4, 5, 6};
    int result[2] = {0};
    counter(arr, 6, result);
    if (result[0] == 9 && result[1] == 12) {
        printf("TASK:counter=1\n");
    } else {
        printf("TASK:counter=0\n");
    }
    return 0;
}
