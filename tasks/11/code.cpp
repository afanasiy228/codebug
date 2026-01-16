#include <bits/stdc++.h>
using namespace std;


int main()  {

    ios::sync_with_stdio(false);

    cin.tie(nullptr);


    int n, m;

    if (!(cin >> n >> m)) return 0;

    vector<string> g(n);

    for (int i = 0; i < n; ++i) cin >> g[i];


    pair<int,int> s {
        -1,-1
    }
    , t {
        -1,-1
    }
    ;

    for (int i = 0; i < n; ++i)  {

        for (int j = 0; j < m; ++j)  {

            if (g[i][j] == 'S') s =  {
                i, j
            }
            ;

            if (g[i][j] == 'T') t =  {
                i, j
            }
            ;

        }

    }


    vector<vector<int>> dist(n, vector<int>(m, -1));

    queue<pair<int,int>> q;

    dist[s.first][s.second] = 0;

    q.push(s);


    int dx[4] =  {
        1, -1, 0, 0
    }
    ;

    int dy[4] =  {
        0, 0, 1, -1
    }
    ;


    while (!q.empty())  {

        auto [x, y] = q.front();

        q.pop();

        for (int k = 0; k < 4; ++k)  {

            int nx = x + dx[k];

            int ny = y + dy[k];

            if (nx < 0 || ny < 0 || nx >= n || ny >= m) continue;


            if (dist[nx][ny] == -1)  {
            // TODO: need to skip walls (#)

                dist[nx][ny] = dist[x][y] + 1;

                q.push( {
                    nx, ny
                }
                );

            }

        }

    }


    cout << dist[t.first][t.second] << "\n";

    return 0;

}

/* ANSWER:
Используй BFS по клеткам, отмечай посещенные.
*/
