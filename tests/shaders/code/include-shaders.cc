#include <stdio.h>
#include <Windows.h>
#include "shaders-include.h"

int main()
{
#define _(name) \
  printf("%p %d\n", my::stuff::name##_Bytes, int(my::stuff::name##_Length));
  SHADER_MAP(_)
#undef _
}
