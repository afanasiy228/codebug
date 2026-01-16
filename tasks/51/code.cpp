#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,m,q;
    if(!(cin>>n>>m>>q)) return 0;
    vector<vector<long long>> a(n+1, vector<long long>(m+1,0));

    for(int i=1;i<=n;i++) for(int j=1;j<=m;j++) cin>>a[i][j];

    vector<vector<long long>> pref(n+1, vector<long long>(m+1,0));

    for(int i=1;i<=n;i++) for(int j=1;j<=m;j++) pref[i][j]=a[i][j]+pref[i-1][j]+pref[i][j-1]-pref[i-1][j-1];

    while(q--) {
        int x1,y1,x2,y2;
        cin>>x1>>y1>>x2>>y2;
        cout<<pref[x2][y2]-pref[x1][y2]-pref[x2][y1]+pref[x1][y1]<<"\n";
    }

}
