int helper_value();
int other_value();

int main()
{
    return helper_value() + other_value() == 50 ? 0 : 1;
}
