#ifndef LAUNCHED_CXX
# error "C++ compile did not run through CXX_LAUNCHER"
#endif

extern "C" int egg();

int main()
{
  return egg();
}
