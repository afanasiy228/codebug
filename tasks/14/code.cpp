#include <bits/stdc++.h>
using namespace std;


int main()  {

    ios::sync_with_stdio(false);

    cin.tie(nullptr);


    string s;

    if (!(cin >> s)) return 0;

    vector<char> st;

    for (char c : s)  {

        if (c == '(' || c == '[') st.push_back(c);

        else  {

            if (st.empty())  {

                cout << "NO\n";

                return 0;

            }

            char t = st.back();

            st.pop_back();


            if ((c == ')' && t != '[') || (c == ']' && t != '('))  {

                cout << "NO\n";

                return 0;

            }

        }

    }

    cout << (st.empty() ? "YES\n" : "NO\n");

    return 0;

}
